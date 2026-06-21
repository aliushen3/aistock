"""BearCase 看空对抗（主线一，入池闸三）。

独立检索反面证据（不复用看多 Agent 检索结果），与看多论点等强度对打。
规则默认 + LLM 增强 seam。对齐 docs/DESIGN.md §6.4 / docs/04-graphrag-design.md §5。
"""

from __future__ import annotations

import uuid

from app.ontology.object_store import make_candidate_entry_id
from app.ontology.property_overlays import merge_product
from app.services import bearcase_store
from app.services.candidate_pool import build_pool
from app.services.graph_store import InMemoryGraphStore
from app.services.llm_client import enhance_bearcase_with_llm, is_llm_enabled
from app.services.value_capture import compute_value_capture
from app.services.vector_store import search_hybrid

COUNTER_QUERY = "风险 技术替代 新增扩产 需求下滑 估值透支 客户集中 库存累积 海外断供"


def _candidate_product(store: InMemoryGraphStore, stock_code: str) -> dict | None:
    company = store.get_company(stock_code)
    if not company:
        return None
    produces = company.get("produces", [])
    if not produces:
        return None
    return merge_product(store.get_product(produces[0]), produces[0])


def _rule_bear_arguments(store: InMemoryGraphStore, item: dict, citations: list[str]) -> list[dict]:
    """七维反证规则派生（逐项必查），返回该候选的看空论点列表。"""
    code = item["stock_code"]
    company = store.get_company(code) or {}
    product = _candidate_product(store, code) or {}
    pid = product.get("id")
    args: list[dict] = []

    def add(dimension, risk, severity, what):
        args.append(
            {
                "stock_code": code,
                "dimension": dimension,
                "risk": risk,
                "severity": severity,
                "probability": "medium",
                "what_would_confirm": what,
                "citations": citations,
            }
        )

    # 估值透支（联动闸一）
    pe = company.get("pe_percentile")
    if pe is not None and pe >= 0.8:
        add("估值透支", f"{item.get('name')} 估值历史分位约 {pe}，预期高度透支", "high",
            "估值分位维持高位且盈利预测下修")
    elif pe is not None and pe >= 0.6:
        add("估值透支", f"{item.get('name')} 估值分位 {pe} 偏高", "medium", "估值进一步抬升而业绩未兑现")

    # 海外断供 / 政策贸易限制
    if product.get("overseas_dependence") == "high":
        add("政策风险", f"「{product.get('name')}」海外依赖度高，面临断供/出口管制风险", "high",
            "出现针对性出口管制或断供事件")

    # 技术替代
    if product.get("substitution_difficulty") == "low":
        add("技术替代", f"「{product.get('name')}」替代难度低，存在替代路线风险", "high",
            "出现成熟替代方案并被下游导入")

    # 新增扩产（联动瓶颈生命周期 easing）
    if product.get("bottleneck_status", "none") != "none" and product.get("expansion_cycle_months", 99) < 18:
        add("新增扩产", f"「{product.get('name')}」扩产周期偏短，供需缺口或较快缓解", "medium",
            "2 年内大量产能释放，现货价格回落")

    # 价值捕获（联动闸二）
    if pid:
        vc = compute_value_capture(pid, code)
        if vc.get("captures_economics") == "no":
            add("客户集中度", f"利润被下游攫取，{item.get('name')} 难以捕获瓶颈稀缺溢价", "high",
                "毛利率持续走低或大客户压价")
        elif vc.get("captures_economics") == "partial":
            add("客户集中度", f"{item.get('name')} 价值捕获能力有限（长协锁价/客户集中）", "medium",
                "长协到期未能提价")

    return args


def generate_bear_cases(store: InMemoryGraphStore, sector_id: str, mode: str, max_candidates: int = 5) -> list[dict]:
    """对融合池前若干候选生成看空论点（纯函数，不持久化）。"""
    pool = build_pool(store, sector_id, mode)[:max_candidates]
    evidence = list(store.evidence.values())
    retrieved = search_hybrid(COUNTER_QUERY, evidence, sector_id=sector_id, top_k=4)
    citations = [r["ref_id"] for r in retrieved if r.get("ref_id")]

    items: list[dict] = []
    for cand in pool:
        bears = _rule_bear_arguments(store, cand, citations)
        for b in bears:
            b["candidate_id"] = make_candidate_entry_id(sector_id, mode, b["stock_code"])
        items.extend(bears)

    if is_llm_enabled() and items:
        enhanced = enhance_bearcase_with_llm(
            {
                "sector_id": sector_id,
                "mode": mode,
                "rule_bear_cases": items,
                "retrieved_evidence": retrieved,
            }
        )
        if enhanced and enhanced.get("bear_cases"):
            llm_items = []
            for b in enhanced["bear_cases"]:
                code = b.get("stock_code")
                if not code:
                    continue
                b.setdefault("citations", citations)
                b["candidate_id"] = make_candidate_entry_id(sector_id, mode, code)
                llm_items.append(b)
            if llm_items:
                items = llm_items
    return items


def generate_and_store_bear_cases(
    sector_id: str, mode: str = "fusion", max_candidates: int = 5, operator: str = "system"
) -> dict:
    """生成 + 持久化，供 Function 与 Agent 复用。"""
    from app.services.graph_store import get_store

    store = get_store()
    if store.get_sector(sector_id) is None:
        raise ValueError(f"赛道不存在: {sector_id}")
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    items = generate_bear_cases(store, sector_id, mode, max_candidates)
    agent_mode = "bear_llm_v1" if is_llm_enabled() else "bear_rule_v1"
    saved = bearcase_store.save_bear_cases(run_id, sector_id, items, agent_mode=agent_mode, operator=operator)
    high_unrebutted = sum(1 for b in saved if b["severity"] == "high" and b["rebuttal_status"] == "unrebutted")
    return {
        "run_id": run_id,
        "sector_id": sector_id,
        "mode": mode,
        "agent_mode": agent_mode,
        "bear_case_count": len(saved),
        "high_unrebutted": high_unrebutted,
        "bear_cases": saved,
    }
