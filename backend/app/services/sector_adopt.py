"""赛道推荐采纳 — 将 Agent 提案写入赛道库。"""

from __future__ import annotations

from app.agents.sector_recommend_agent import make_sector_id_for_adopt
from app.ontology import pg_store
from app.ontology.property_overlays import set_sector_property
from app.services.graph_store import get_store, invalidate_store_cache, set_store_from_db
from app.services.sector_bootstrap import bootstrap_sector
from app.services.sector_recommendations import get_recommendation, update_status


def adopt_recommendation(
    rec_id: str,
    operator: str = "analyst",
    auto_bootstrap: bool = True,
) -> dict:
    rec = get_recommendation(rec_id)
    if rec is None:
        raise ValueError(f"推荐不存在: {rec_id}")
    if rec["status"] == "adopted":
        raise ValueError("该推荐已采纳")
    if rec["status"] == "dismissed":
        raise ValueError("该推荐已驳回，无法采纳")

    sector_id = make_sector_id_for_adopt(rec["sector_name"], rec.get("sector_id"))
    store = get_store()
    existing = store.get_sector(sector_id)

    created = False
    if existing is None:
        if pg_store.is_db_enabled():
            created = pg_store.insert_sector(
                sector_id=sector_id,
                name=rec["sector_name"],
                demand_growth_hint=rec.get("demand_growth_hint"),
                terminal_products=rec.get("terminal_products") or [],
                attrs={"source": "sector_recommend_agent", "rec_id": rec_id},
            )
            if created:
                set_store_from_db(True)
                invalidate_store_cache()
        else:
            raise ValueError("数据库未启用，无法创建新赛道，请配置 PostgreSQL")
    else:
        set_sector_property(sector_id, "status", "beta_candidate")
        if rec.get("demand_growth_hint") is not None:
            set_sector_property(sector_id, "demand_growth_hint", rec["demand_growth_hint"])

    update_status(rec_id, "adopted")
    sector = get_store().get_sector(sector_id)
    bootstrap_result = None
    if auto_bootstrap:
        bootstrap_result = bootstrap_sector(sector_id)
    return {
        "rec_id": rec_id,
        "sector_id": sector_id,
        "sector_name": rec["sector_name"],
        "created": created,
        "status": sector.get("status") if sector else "beta_candidate",
        "message": "已采纳为 beta_candidate，请研究员执行 ConfirmSectorBeta",
        "bootstrap": bootstrap_result,
        "operator": operator,
    }


def dismiss_recommendation(rec_id: str, operator: str = "analyst") -> dict:
    rec = get_recommendation(rec_id)
    if rec is None:
        raise ValueError(f"推荐不存在: {rec_id}")
    update_status(rec_id, "dismissed")
    return {"rec_id": rec_id, "status": "dismissed", "operator": operator}
