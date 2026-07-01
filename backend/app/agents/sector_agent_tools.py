"""赛道推荐 Agent 工具集 — ReAct 可调用工具注册表。"""

from __future__ import annotations

import json
from typing import Any

from app.ontology.object_store import list_sectors
from app.services.graph_store import get_store
from app.services.metrics import get_sector_metrics_summary
from app.services.sector_theme_extractor import extract_sector_themes_from_reports
from app.services.vector_store import search_documents, search_evidence
from app.services.watchlist_service import (
    build_dynamic_watchlist,
    get_watchlist,
    invalidate_watchlist_cache,
)

BETA_CRITERIA = {
    "demand_growth_threshold": 0.20,
    "capex_positive": True,
    "min_research_support": 1,
    "description": "下游需求复合增速>20%、资本开支同比为正、有研报/公告证据支撑",
}

TOOL_SPECS: list[dict] = [
    {"name": "list_sectors", "description": "列出系统已有赛道及确认状态", "input_schema": {}},
    {
        "name": "collect_metrics_signals",
        "description": "采集赛道产业指标信号（需求增速、资本开支、产能利用率）",
        "input_schema": {"sector_id": "可选，不传则全部赛道"},
    },
    {
        "name": "search_research_evidence",
        "description": "混合检索研报与种子证据",
        "input_schema": {"query": "检索词", "sector_id": "可选"},
    },
    {
        "name": "extract_sector_themes_from_reports",
        "description": "从已上传研报自动抽取潜在新赛道主题",
        "input_schema": {"focus": "可选关注方向"},
    },
    {
        "name": "get_watchlist",
        "description": "获取动态观察清单（研报主题+Ontology+ODS/上传元数据）",
        "input_schema": {"focus": "可选关注方向"},
    },
    {"name": "get_beta_criteria", "description": "获取 Beta 赛道判定标准", "input_schema": {}},
    {
        "name": "cold_start_industry_signals",
        "description": "冷启动信号：东财行业板块涨跌排名 + 同花顺当日题材热点（空图无证据时的候选来源）",
        "input_schema": {"top_n": "默认 8"},
    },
]


def tool_list_sectors() -> list[dict]:
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "status": s.get("status"),
            "demand_growth_hint": s.get("demand_growth_hint"),
            "human_confirmed": s.get("human_confirmed", False),
            "terminal_products": s.get("terminal_products", []),
            "product_count": len(get_store().list_products(s["id"])),
        }
        for s in list_sectors()
    ]


def tool_collect_metrics_signals(sector_id: str | None = None) -> list[dict]:
    store = get_store()
    sector_ids = [sector_id] if sector_id else [s["id"] for s in store.list_sectors()]
    signals = []
    for sid in sector_ids:
        summary = get_sector_metrics_summary(sid)
        if not summary:
            continue
        sector = store.get_sector(sid)
        signals.append(
            {
                "sector_id": sid,
                "sector_name": sector["name"] if sector else sid,
                **summary,
            }
        )
    return signals


def tool_search_research_evidence(query: str, sector_id: str | None = None, top_k: int = 8) -> list[dict]:
    store = get_store()
    evidence = list(store.evidence.values())
    ev_hits = search_evidence(query, evidence, top_k=top_k)
    doc_hits = search_documents(query, sector_id=sector_id, top_k=top_k)
    merged: dict[str, dict] = {}
    for h in ev_hits + doc_hits:
        rid = h.get("ref_id")
        if rid and rid not in merged:
            merged[rid] = h
    return list(merged.values())[:top_k]


def tool_extract_sector_themes(focus: str | None = None) -> dict:
    invalidate_watchlist_cache()
    return extract_sector_themes_from_reports(focus=focus)


def tool_get_watchlist(focus: str | None = None) -> list[dict]:
    return get_watchlist(focus=focus, refresh=True)


def tool_get_beta_criteria() -> dict:
    return BETA_CRITERIA


def watchlist_needs_cold_start(watchlist: list[dict]) -> bool:
    """空图时：无观察项，或仅有用户 focus 且无证据时，需拉行业轮动/热点做冷启动。"""
    if not watchlist:
        return True
    return all(
        item.get("source") == "focus" and not item.get("evidence_refs")
        for item in watchlist
    )


def tool_cold_start_industry_signals(top_n: int = 8) -> dict:
    """冷启动证据源：行业板块综合排序（多日涨幅+资金净流入+题材热度加权）。

    直连东财/同花顺，任一源失败均安全降级为空，不阻断赛道推荐主流程。
    输出兼容旧结构：industry_ranking（已综合排序）+ hot_themes。
    """
    from app.services.a_share_data_source import rank_industry_boards

    out: dict[str, Any] = {"industry_ranking": [], "hot_themes": []}
    try:
        ranked = rank_industry_boards(top_n=top_n)
        out["industry_ranking"] = ranked.get("ranking", [])
        out["hot_themes"] = ranked.get("hot_themes", [])
        out["ranking_period"] = ranked.get("period")
        out["ranking_weights"] = ranked.get("weights")
    except Exception:  # noqa: BLE001 网络/风控失败时降级
        pass
    return out


def execute_tool(name: str, action_input: dict | None = None) -> Any:
    """ReAct 工具分发。"""
    inp = action_input or {}
    if name == "list_sectors":
        return tool_list_sectors()
    if name == "collect_metrics_signals":
        return tool_collect_metrics_signals(inp.get("sector_id"))
    if name == "search_research_evidence":
        return tool_search_research_evidence(inp.get("query", "高景气 产业链"), inp.get("sector_id"))
    if name == "extract_sector_themes_from_reports":
        result = tool_extract_sector_themes(inp.get("focus"))
        invalidate_watchlist_cache()
        return result
    if name == "get_watchlist":
        return tool_get_watchlist(inp.get("focus"))
    if name == "get_beta_criteria":
        return tool_get_beta_criteria()
    if name == "cold_start_industry_signals":
        return tool_cold_start_industry_signals(int(inp.get("top_n") or 8))
    raise ValueError(f"未知工具: {name}")


def build_agent_context(focus: str | None = None, query: str | None = None) -> dict:
    """预采集上下文（规则模式 / ReAct 初始状态）。"""
    watchlist_payload = build_dynamic_watchlist(focus=focus, refresh=True)
    search_q = " ".join(filter(None, [focus, query, "高景气 需求增长 资本开支 瓶颈 产业链"]))
    existing_sectors = tool_list_sectors()
    watchlist = watchlist_payload["watchlist"]
    context = {
        "focus": focus,
        "query": query,
        "beta_criteria": tool_get_beta_criteria(),
        "existing_sectors": existing_sectors,
        "metrics_signals": tool_collect_metrics_signals(),
        "watchlist": watchlist,
        "watchlist_meta": {
            "dynamic": True,
            "watchlist_count": watchlist_payload["watchlist_count"],
            "source_counts": watchlist_payload["source_counts"],
        },
        "report_themes": watchlist_payload["report_themes"],
        "evidence_hits": tool_search_research_evidence(search_q, top_k=10),
    }
    # 冷启动：空图且观察清单无有效证据时，用信号层行业轮动/热点提供候选
    if not existing_sectors and watchlist_needs_cold_start(watchlist):
        context["cold_start_signals"] = tool_cold_start_industry_signals()
    return context
