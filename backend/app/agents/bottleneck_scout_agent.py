"""瓶颈哨兵智能体 — 全产品提示分扫描 → 瓶颈确认提案。"""

from __future__ import annotations

import uuid

from app.agents.bottleneck_agent_tools import (
    tool_calc_product_hint,
    tool_list_sector_products,
    tool_search_bottleneck_evidence,
)
from app.services.bottleneck_recommendations import save_recommendations
from app.services.graph_store import get_store
from app.services.object_set_alerts import push_bottleneck_recommendation_alerts
from app.services.workflow import is_sector_confirmed


def _build_rationale(hint: dict, metrics: dict | None) -> str:
    parts = [f"提示分 {hint['hint_score']}（{hint['hint_level']}）"]
    top_rules = sorted(hint.get("hit_rules", []), key=lambda x: -x.get("score", 0))[:2]
    for r in top_rules:
        parts.append(f"{r.get('rule')}={r.get('value')}")
    if metrics and metrics.get("high_utilization_products"):
        names = [x.get("product_name", "") for x in metrics["high_utilization_products"][:2]]
        parts.append(f"高产能利用率: {', '.join(names)}")
    return "；".join(parts)


def run_bottleneck_scout_agent(
    sector_id: str,
    min_hint_level: str = "hint_medium",
    operator: str = "analyst",
) -> dict:
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise ValueError(f"赛道不存在: {sector_id}")

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    level_rank = {"none": 0, "hint_low": 1, "hint_medium": 2, "hint_high": 3}
    min_rank = level_rank.get(min_hint_level, 2)

    from app.services.metrics import get_sector_metrics_summary

    metrics = get_sector_metrics_summary(sector_id)
    proposals: list[dict] = []

    for row in tool_list_sector_products(sector_id):
        if row.get("bottleneck_status") == "bottleneck_confirmed":
            continue
        hint = tool_calc_product_hint(row["product_id"])
        if hint.get("error"):
            continue
        if level_rank.get(hint["hint_level"], 0) < min_rank:
            continue

        evidence = tool_search_bottleneck_evidence(sector_id, hint["product_name"])
        evidence_refs = [
            {"ref_id": e.get("ref_id"), "excerpt": (e.get("excerpt") or "")[:120]}
            for e in evidence[:3]
        ]
        proposals.append(
            {
                "product_id": hint["product_id"],
                "product_name": hint["product_name"],
                "hint_score": hint["hint_score"],
                "hint_level": hint["hint_level"],
                "hit_rules": hint["hit_rules"],
                "rationale": _build_rationale(hint, metrics),
                "evidence_refs": evidence_refs,
            }
        )

    proposals.sort(key=lambda x: -x["hint_score"])
    saved = save_recommendations(
        run_id=run_id,
        sector_id=sector_id,
        items=proposals,
        agent_mode="scout_rule_v1",
        operator=operator,
    )
    alerts = push_bottleneck_recommendation_alerts(saved, run_id)

    return {
        "run_id": run_id,
        "agent": "bottleneck_scout_v1",
        "agent_mode": "scout_rule_v1",
        "sector_id": sector_id,
        "sector_confirmed": is_sector_confirmed(sector_id),
        "scanned_products": len(tool_list_sector_products(sector_id)),
        "recommendations": saved,
        "alerts_pushed": alerts,
        "disclaimer": "瓶颈提案须经 ConfirmBottleneck 人工确认后方可生效",
    }
