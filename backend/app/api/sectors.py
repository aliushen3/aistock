from enum import Enum

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/sectors", tags=["sectors"])


class SectorStatus(str, Enum):
    BETA_CANDIDATE = "beta_candidate"
    BETA_CONFIRMED = "beta_confirmed"


class Sector(BaseModel):
    id: str
    name: str
    status: SectorStatus
    demand_growth_hint: float | None = None
    human_confirmed: bool = False


@router.get("")
def list_sectors():
    """列出赛道；高景气需研究员确认后才为 beta_confirmed。"""
    return {
        "items": [
            Sector(
                id="sector_ai_compute",
                name="AI算力",
                status=SectorStatus.BETA_CONFIRMED,
                demand_growth_hint=35.0,
                human_confirmed=True,
            ),
        ],
        "note": "beta_candidate 需人工确认后方可进入后续流程",
    }


@router.post("/{sector_id}/confirm")
def confirm_sector(sector_id: str, confirmed: bool, reason: str):
    """研究员确认/驳回赛道景气。"""
    return {
        "sector_id": sector_id,
        "confirmed": confirmed,
        "reason": reason,
        "status": "beta_confirmed" if confirmed else "rejected",
    }
