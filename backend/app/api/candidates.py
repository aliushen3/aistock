from enum import Enum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.audit import audit_log
from app.services.candidate_pool import build_pool, set_state
from app.services.graph_store import get_store

router = APIRouter(prefix="/candidates", tags=["candidates"])


class PoolMode(str, Enum):
    BUY_SIDE = "buy_side"
    SERENITY = "serenity"
    FUSION = "fusion"


class PoolEntryStatus(str, Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ConfirmPoolRequest(BaseModel):
    sector_id: str
    mode: PoolMode = PoolMode.FUSION
    stock_codes: list[str]
    action: PoolEntryStatus
    reason: str = Field(..., min_length=5)
    operator: str = "analyst"


@router.get("")
def list_candidates(sector_id: str, mode: PoolMode = PoolMode.FUSION):
    """获取候选池；默认均为 pending，需人工确认入池。"""
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {sector_id}")
    items = build_pool(store, sector_id, mode.value)
    return {
        "sector_id": sector_id,
        "mode": mode,
        "count": len(items),
        "items": items,
        "note": "所有候选 status=pending，须调用 /confirm 后方可入正式池；提示分不构成投资建议",
    }


@router.post("/confirm")
def confirm_candidates(req: ConfirmPoolRequest):
    """研究员/基金经理确认入池或否决（人机协同门控：入池前必经）。"""
    store = get_store()
    if store.get_sector(req.sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {req.sector_id}")
    for code in req.stock_codes:
        set_state(req.sector_id, req.mode.value, code, req.action.value, req.reason, req.operator)
    entry = audit_log.record(
        action="confirm_candidates",
        operator=req.operator,
        target=f"{req.sector_id}:{req.mode.value}",
        detail={"stock_codes": req.stock_codes, "action": req.action.value, "reason": req.reason},
    )
    return {
        "action": req.action,
        "stock_codes": req.stock_codes,
        "reason": req.reason,
        "audit_id": entry.id,
        "message": f"已记录审计日志 #{entry.id}，{len(req.stock_codes)} 个标的状态更新为 {req.action.value}",
    }


@router.get("/audit")
def list_audit():
    """审计日志（演示用）。"""
    return {"items": audit_log.list_all()}
