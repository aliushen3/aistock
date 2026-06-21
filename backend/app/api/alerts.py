from fastapi import APIRouter, HTTPException

from app.services.graph_store import get_store
from app.services.object_set_alerts import evaluate_alerts
from app.services.owl_validator import validate_sector_graph

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/global")
def get_global_alerts():
    """全局告警 — 含赛道推荐等待采纳。"""
    from app.services.object_set_alerts import evaluate_global_alerts

    items = evaluate_global_alerts()
    return {"count": len(items), "items": items}


@router.get("/sector/{sector_id}")
def get_sector_alerts(sector_id: str, mode: str = "fusion"):
    """Object Set 告警 — 待确认瓶颈、待入池候选等。"""
    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")
    items = evaluate_alerts(sector_id, mode)
    return {"sector_id": sector_id, "count": len(items), "items": items}


@router.get("/ontology/validate/{sector_id}")
def validate_ontology(sector_id: str):
    """OWL 一致性校验。"""
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")
    return validate_sector_graph(store, sector_id)
