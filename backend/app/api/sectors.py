from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.audit import audit_log
from app.services.graph_store import get_store

router = APIRouter(prefix="/sectors", tags=["sectors"])


class ConfirmSectorRequest(BaseModel):
    confirmed: bool
    reason: str = Field(..., min_length=5)
    operator: str = "analyst"


@router.get("")
def list_sectors():
    """列出赛道；高景气需研究员确认后才为 beta_confirmed。"""
    store = get_store()
    return {
        "items": [
            {
                "id": s["id"],
                "name": s["name"],
                "status": s.get("status"),
                "demand_growth_hint": s.get("demand_growth_hint"),
                "human_confirmed": s.get("human_confirmed", False),
            }
            for s in store.list_sectors()
        ],
        "note": "beta_candidate 需人工确认后方可进入后续流程",
    }


@router.post("/{sector_id}/confirm")
def confirm_sector(sector_id: str, req: ConfirmSectorRequest):
    """研究员确认/驳回赛道景气（人机协同门控 1）。"""
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {sector_id}")
    status = "beta_confirmed" if req.confirmed else "rejected"
    audit_log.record(
        action="confirm_sector",
        operator=req.operator,
        target=sector_id,
        detail={"confirmed": req.confirmed, "reason": req.reason, "status": status},
    )
    return {"sector_id": sector_id, "status": status, "reason": req.reason}
