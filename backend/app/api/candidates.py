from enum import Enum

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/candidates", tags=["candidates"])


class PoolMode(str, Enum):
    BUY_SIDE = "buy_side"
    SERENITY = "serenity"
    FUSION = "fusion"


class PoolEntryStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ConfirmPoolRequest(BaseModel):
    stock_codes: list[str]
    action: PoolEntryStatus
    reason: str = Field(..., min_length=5)


@router.get("")
def list_candidates(sector_id: str, mode: PoolMode = PoolMode.FUSION):
    """获取候选池；默认均为 pending，需人工确认入池。"""
    return {
        "sector_id": sector_id,
        "mode": mode,
        "items": [],
        "note": "所有候选 status=pending，须调用 /confirm 后方可入正式池",
    }


@router.post("/confirm")
def confirm_candidates(req: ConfirmPoolRequest):
    """研究员/基金经理确认入池或否决。"""
    return {
        "action": req.action,
        "stock_codes": req.stock_codes,
        "reason": req.reason,
        "message": "已记录审计日志，同步知识库待实现",
    }
