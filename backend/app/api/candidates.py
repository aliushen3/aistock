from enum import Enum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ontology.action_executor import ActionError, action_executor
from app.ontology.object_store import make_candidate_entry_id
from app.services.audit import audit_log
from app.services.candidate_pool import build_pool
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
    """研究员/基金经理确认入池或否决 — 委托 Ontology Action 执行。"""
    store = get_store()
    if store.get_sector(req.sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {req.sector_id}")

    action_type = "ApprovePoolEntry" if req.action == PoolEntryStatus.CONFIRMED else "RejectPoolEntry"
    results = []
    errors = []
    for code in req.stock_codes:
        entry_id = make_candidate_entry_id(req.sector_id, req.mode.value, code)
        try:
            r = action_executor.execute_with_params(
                action_type=action_type,
                target_type="CandidatePoolEntry",
                target_id=entry_id,
                params={"reason": req.reason},
                operator=req.operator,
            )
            results.append({"stock_code": code, "audit_id": r.audit_id})
        except ActionError as e:
            errors.append({"stock_code": code, "error": e.message})

    if errors and not results:
        raise HTTPException(status_code=400, detail={"errors": errors})

    last_audit = results[-1]["audit_id"] if results else None
    return {
        "action": req.action,
        "stock_codes": req.stock_codes,
        "reason": req.reason,
        "audit_id": last_audit,
        "ontology_action": action_type,
        "processed": len(results),
        "errors": errors,
        "message": f"已通过 Ontology Action {action_type} 处理 {len(results)} 个标的",
    }


@router.get("/audit")
def list_audit():
    """审计日志（演示用）。"""
    return {"items": audit_log.list_all()}
