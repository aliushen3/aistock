from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ontology.action_executor import ActionError, action_executor
from app.ontology.object_store import list_sectors as ont_list_sectors

router = APIRouter(prefix="/sectors", tags=["sectors"])


class ConfirmSectorRequest(BaseModel):
    confirmed: bool
    reason: str = Field(..., min_length=5)
    operator: str = "analyst"


@router.get("")
def list_sectors():
    """列出赛道；高景气需研究员确认后才为 beta_confirmed。"""
    return {
        "items": [
            {
                "id": s["id"],
                "name": s["name"],
                "status": s.get("status"),
                "demand_growth_hint": s.get("demand_growth_hint"),
                "human_confirmed": s.get("human_confirmed", False),
            }
            for s in ont_list_sectors()
        ],
        "note": "beta_candidate 需人工确认后方可进入后续流程",
    }


@router.post("/{sector_id}/confirm")
def confirm_sector(sector_id: str, req: ConfirmSectorRequest):
    """研究员确认/驳回赛道景气 — 委托 Ontology Action ConfirmSectorBeta。"""
    from app.services.graph_store import get_store, invalidate_store_cache

    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {sector_id}")

    if not req.confirmed:
        from app.ontology.object_store import set_object_property

        set_object_property("Sector", sector_id, "status", "rejected")
        set_object_property("Sector", sector_id, "human_confirmed", False)
        # 状态已写入 DB/overlay，失效缓存快照，确保后续 GET /sectors 读到最新值
        invalidate_store_cache()
        return {"sector_id": sector_id, "status": "rejected", "reason": req.reason}

    try:
        result = action_executor.execute_with_params(
            action_type="ConfirmSectorBeta",
            target_type="Sector",
            target_id=sector_id,
            params={"reason": req.reason},
            operator=req.operator,
        )
    except ActionError as e:
        raise HTTPException(status_code=400, detail=e.message) from e

    invalidate_store_cache()
    return {
        "sector_id": sector_id,
        "status": "beta_confirmed",
        "reason": req.reason,
        "audit_id": result.audit_id,
        "ontology_action": "ConfirmSectorBeta",
    }
