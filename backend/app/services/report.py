"""GraphRAG 投研逻辑报告生成（一期：规则模板版）。

一期不接入 LLM，逻辑链与引用全部来自图谱事实与证据，保证可追溯、零幻觉；
`generate_logic_chain` / `generate_counter_arguments` 预留 LLM 接入 seam。
报告 status 恒为 draft，须经研究员审核后方可 published（见 docs/04-graphrag-design.md）。
"""

from __future__ import annotations

import itertools
from datetime import datetime, timezone

from app.services.candidate_pool import build_fusion_pool
from app.services.graph_store import InMemoryGraphStore
from app.services.hint_score import calc_bottleneck_hint
from app.services.serenity_trace import serenity_reverse_trace

_report_seq = itertools.count(1)
_report_store: dict[str, dict] = {}

DISCLAIMER = "本报告由系统辅助生成，逻辑链与引用均来自图谱事实，仅供投研参考，不构成投资建议；须经研究员审核后方可使用。"


def _cite(store: InMemoryGraphStore, product: dict) -> list[dict]:
    return [
        {"ref_id": e["id"], "source_type": e["source_type"], "source_ref": e["source_ref"], "excerpt": e["excerpt"]}
        for e in store.resolve_evidence(product.get("provenance_ids", []))
    ]


def generate_logic_chain(store: InMemoryGraphStore, sector_id: str) -> tuple[list[dict], list[dict]]:
    """返回 (logic_chain, all_citations)。LLM 接入点：可用本函数输出做 RAG 上下文。"""
    sector = store.get_sector(sector_id)
    chain: list[dict] = []
    citations: dict[str, dict] = {}

    # Step 1：赛道 Beta
    terminals = sector.get("terminal_products", [])
    beta_cites = []
    for tid in terminals:
        for c in _cite(store, store.get_product(tid)):
            citations[c["ref_id"]] = c
            beta_cites.append(c["ref_id"])
    chain.append(
        {
            "step": 1,
            "type": "beta_thesis",
            "claim": f"{sector['name']} 赛道处于高景气（需求增速提示 {sector.get('demand_growth_hint')}%），具备整体行情基础。",
            "citations": beta_cites,
            "confidence": "high" if sector.get("human_confirmed") else "medium",
            "human_confirmed": sector.get("human_confirmed", False),
        }
    )

    # Step 2：瓶颈环节（取提示分最高的已确认/疑似瓶颈）
    bottlenecks = [
        p for p in store.list_products(sector_id)
        if p.get("bottleneck_status") in ("bottleneck_hint", "bottleneck_confirmed")
    ]
    bottlenecks.sort(key=lambda p: -calc_bottleneck_hint(p).total)
    for p in bottlenecks[:3]:
        hint = calc_bottleneck_hint(p)
        cites = _cite(store, p)
        for c in cites:
            citations[c["ref_id"]] = c
        chain.append(
            {
                "step": 2,
                "type": "bottleneck",
                "claim": f"「{p['name']}」为瓶颈环节（{p['bottleneck_status']}，提示分 {hint.total}）：扩产周期 {p['expansion_cycle_months']} 月、CR4 {p['cr4_concentration']}、海外依赖 {p['overseas_dependence']}。",
                "citations": [c["ref_id"] for c in cites],
                "confidence": "high" if p["bottleneck_status"] == "bottleneck_confirmed" else "medium",
                "human_confirmed": p["bottleneck_status"] == "bottleneck_confirmed",
            }
        )

    # Step 3：Serenity 逆向小众环节
    paths = serenity_reverse_trace(store, terminals, sector_id)
    for path in paths[:3]:
        p = store.get_product(path.niche_product_id)
        cites = _cite(store, p)
        for c in cites:
            citations[c["ref_id"]] = c
        chain.append(
            {
                "step": 3,
                "type": "serenity_niche",
                "claim": f"逆向溯源至小众咽喉环节「{path.niche_product_name}」（{path.hop_count} 跳，提示分 {path.serenity_hint}）：{path.companies[0]['name'] if path.companies else ''} 等低拥挤标的。路径：{' → '.join(path.node_names)}",
                "citations": [c["ref_id"] for c in cites],
                "confidence": "medium",
                "human_confirmed": False,
            }
        )

    return chain, list(citations.values())


def generate_counter_arguments(store: InMemoryGraphStore, sector_id: str) -> list[dict]:
    """反证 checklist（固定项），从图谱数据派生严重度。LLM 接入点：可改为 LLM 逐项论证。"""
    sector = store.get_sector(sector_id)
    products = store.list_products(sector_id)
    fusion = build_fusion_pool(store, sector_id)

    has_low_sub = any(p.get("substitution_difficulty") == "low" for p in products if p.get("layer") != "terminal")
    short_expansion = [p for p in products if p.get("bottleneck_status", "none") != "none" and p.get("expansion_cycle_months", 0) < 18]
    demand = sector.get("demand_growth_hint", 0)
    # 估值分位取候选中最高
    pe_vals = [store.get_company(x["stock_code"]).get("pe_percentile", 0) for x in fusion if store.get_company(x["stock_code"])]
    max_pe = max(pe_vals) if pe_vals else 0
    overseas = [p for p in products if p.get("overseas_dependence") == "high"]

    def lvl(cond_high, cond_med):
        return "高" if cond_high else ("中" if cond_med else "低")

    return [
        {
            "risk": "技术替代",
            "severity": lvl(has_low_sub, False),
            "note": "存在低替代难度环节，需警惕替代路线" if has_low_sub else "关键环节替代难度普遍较高，替代风险有限",
        },
        {
            "risk": "新增扩产",
            "severity": lvl(False, bool(short_expansion)),
            "note": f"以下瓶颈环节扩产周期偏短，供需缺口或较快缓解：{[p['name'] for p in short_expansion]}" if short_expansion else "瓶颈环节扩产周期普遍 >=18 月，短期供给刚性",
        },
        {
            "risk": "需求下滑",
            "severity": lvl(demand < 10, demand < 20),
            "note": f"赛道需求增速提示 {demand}%，需跟踪下游资本开支与出货",
        },
        {
            "risk": "估值透支",
            "severity": lvl(max_pe >= 0.8, max_pe >= 0.6),
            "note": f"候选中最高 PE 历史分位约 {max_pe}，高分位标的需警惕透支",
        },
        {
            "risk": "政策/贸易限制",
            "severity": lvl(len(overseas) >= 3, len(overseas) >= 1),
            "note": f"{len(overseas)} 个环节海外依赖度高，出口管制/断供为主要外部风险",
        },
    ]


def generate_report(store: InMemoryGraphStore, sector_id: str, mode: str) -> dict:
    chain, citations = generate_logic_chain(store, sector_id)
    counters = generate_counter_arguments(store, sector_id)
    fusion = build_fusion_pool(store, sector_id)
    candidates = [
        {
            "stock_code": x["stock_code"],
            "name": x["name"],
            "role": x.get("tag"),
            "priority": x.get("priority"),
            "thesis_summary": x["rationale"],
        }
        for x in fusion
    ]
    unverified = [c["claim"] for c in chain if not c["citations"]]

    report_id = f"rpt_{next(_report_seq):04d}"
    report = {
        "report_id": report_id,
        "status": "draft",
        "sector_id": sector_id,
        "mode": mode,
        "generated_by": "rule_template_v1 (未接入LLM)",
        "logic_chain": chain,
        "counter_arguments": counters,
        "candidates": candidates,
        "citations": citations,
        "unverified_claims": unverified,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER,
    }
    _report_store[report_id] = report
    return report


def get_report(report_id: str) -> dict | None:
    return _report_store.get(report_id)


def review_report(report_id: str, action: str, comments: str) -> dict | None:
    report = _report_store.get(report_id)
    if report is None:
        return None
    report["status"] = "published" if action == "approve" else "draft"
    report["review"] = {"action": action, "comments": comments}
    return report
