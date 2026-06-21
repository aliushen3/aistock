"""候选融合智能体 — 双逻辑池合并与可解释排序说明。"""

from __future__ import annotations

import uuid

from app.services.candidate_pool import build_pool
from app.services.graph_store import get_store
from app.services.workflow import is_sector_confirmed


def run_candidate_fusion_agent(
    sector_id: str,
    mode: str = "fusion",
    operator: str = "analyst",
) -> dict:
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise ValueError(f"赛道不存在: {sector_id}")

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    pool = build_pool(store, sector_id, mode)
    p0 = [x for x in pool if x.get("priority") == "P0"]
    buy_side = build_pool(store, sector_id, "buy_side")
    serenity = build_pool(store, sector_id, "serenity")

    rationales = []
    for item in pool[:5]:
        rationales.append(
            {
                "stock_code": item["stock_code"],
                "name": item.get("name"),
                "priority": item.get("priority"),
                "rationale": item.get("rationale"),
                "in_buy_side": item["stock_code"] in {x["stock_code"] for x in buy_side},
                "in_serenity": item["stock_code"] in {x["stock_code"] for x in serenity},
            }
        )

    return {
        "run_id": run_id,
        "agent": "candidate_fusion_v1",
        "agent_mode": "pool_rank_v1",
        "sector_id": sector_id,
        "sector_confirmed": is_sector_confirmed(sector_id),
        "mode": mode,
        "operator": operator,
        "agent_summary": (
            f"融合池 {len(pool)} 只候选，P0 共振 {len(p0)} 只"
            f"（买方池 {len(buy_side)} + Serenity 池 {len(serenity)}）"
        ),
        "candidate_count": len(pool),
        "p0_count": len(p0),
        "top_candidates": rationales,
        "disclaimer": "排序说明仅供参考，入池须 ApprovePoolEntry 人工确认",
    }
