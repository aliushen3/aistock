"""GraphRAG 混合推理 — 图谱事实 + 向量检索 + LLM/规则生成。"""

from __future__ import annotations

from app.services.graph_store import InMemoryGraphStore
from app.services.hint_score import calc_bottleneck_hint
from app.services.llm_client import enhance_report_with_llm, is_llm_enabled
from app.services.report import (
    DISCLAIMER,
    generate_counter_arguments,
    generate_logic_chain,
)
from app.services.vector_store import search_hybrid


def build_rag_context(store: InMemoryGraphStore, sector_id: str, mode: str) -> dict:
    sector = store.get_sector(sector_id)
    products = store.list_products(sector_id)
    evidence = list(store.evidence.values())
    query = f"{sector['name']} 瓶颈 产业链 {' '.join(p['name'] for p in products[:5])}"
    retrieved = search_hybrid(query, evidence, sector_id=sector_id, top_k=6)

    bottlenecks = []
    for p in products:
        if p.get("bottleneck_status") in ("bottleneck_hint", "bottleneck_confirmed"):
            hint = calc_bottleneck_hint(p)
            bottlenecks.append(
                {
                    "product_id": p["id"],
                    "name": p["name"],
                    "status": p.get("bottleneck_status"),
                    "hint_score": hint.total,
                    "expansion_months": p.get("expansion_cycle_months"),
                }
            )

    return {
        "sector": {
            "id": sector_id,
            "name": sector["name"],
            "status": sector.get("status"),
            "demand_growth_hint": sector.get("demand_growth_hint"),
        },
        "mode": mode,
        "bottlenecks": sorted(bottlenecks, key=lambda x: -x["hint_score"])[:5],
        "retrieved_evidence": retrieved,
        "graph_facts": {
            "product_count": len(products),
            "company_count": len(store.companies),
            "relation_count": len(store.relations),
        },
    }


def generate_graphrag_report(
    store: InMemoryGraphStore, sector_id: str, mode: str
) -> tuple[dict, str]:
    """返回 (report_fields, engine_label)。"""
    chain, citations = generate_logic_chain(store, sector_id)
    counters = generate_counter_arguments(store, sector_id)
    context = build_rag_context(store, sector_id, mode)

    # 将检索到的额外证据并入 citations
    cite_map = {c["ref_id"]: c for c in citations}
    for r in context["retrieved_evidence"]:
        rid = r.get("ref_id")
        if rid and rid not in cite_map:
            cite_map[rid] = {
                "ref_id": rid,
                "source_type": r.get("source_type"),
                "source_ref": r.get("source_ref"),
                "excerpt": r.get("excerpt"),
            }
    all_citations = list(cite_map.values())

    engine = "graphrag_hybrid_v1"
    if is_llm_enabled():
        llm_out = enhance_report_with_llm({**context, "rule_chain": chain, "rule_counters": counters})
        if llm_out and llm_out.get("logic_chain"):
            chain = llm_out["logic_chain"]
            if llm_out.get("counter_arguments"):
                counters = llm_out["counter_arguments"]
            engine = f"graphrag_llm_v1 ({context['retrieved_evidence'][0]['retrieval'] if context['retrieved_evidence'] else 'graph'})"
        else:
            engine = "graphrag_hybrid_v1 (LLM降级)"
    else:
        # 规则链补充检索证据引用
        if context["retrieved_evidence"] and chain:
            extra_refs = [r["ref_id"] for r in context["retrieved_evidence"][:3] if r.get("ref_id")]
            if extra_refs:
                chain.append(
                    {
                        "step": len(chain) + 1,
                        "type": "rag_retrieval",
                        "claim": f"混合检索命中 {len(extra_refs)} 条相关证据，支撑赛道逻辑链。",
                        "citations": extra_refs,
                        "confidence": "medium",
                        "human_confirmed": False,
                    }
                )

    unverified = [c["claim"] for c in chain if not c.get("citations")]
    return (
        {
            "logic_chain": chain,
            "counter_arguments": counters,
            "citations": all_citations,
            "unverified_claims": unverified,
            "rag_context": {
                "retrieval_count": len(context["retrieved_evidence"]),
                "retrieval_mode": context["retrieved_evidence"][0]["retrieval"]
                if context["retrieved_evidence"]
                else "none",
            },
            "disclaimer": DISCLAIMER,
        },
        engine,
    )
