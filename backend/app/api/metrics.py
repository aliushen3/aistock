from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.hint_calibration import (
    calibration_summary,
    list_outcomes,
    resolve_outcome,
    suggest_weight_adjustments,
)
from app.services.metrics import dashboard_summary, list_sector_metrics
from app.services.workflow import WorkflowGateError, require_sector_confirmed

router = APIRouter(prefix="/metrics", tags=["metrics"])


class ResolveOutcomeRequest(BaseModel):
    outcome_status: str = Field(..., description="fulfilled | false_positive | inconclusive")
    operator: str = "analyst"


@router.get("/sector/{sector_id}")
def get_sector_metrics(sector_id: str):
    """产业指标时间序列（产能、价格、扩产等）。"""
    return {"sector_id": sector_id, "items": list_sector_metrics(sector_id)}


@router.get("/sector/{sector_id}/dashboard")
def get_dashboard(sector_id: str):
    """产业跟踪看板汇总。"""
    try:
        require_sector_confirmed(sector_id)
    except WorkflowGateError as e:
        if e.code == "sector_not_confirmed":
            return {
                "sector_id": sector_id,
                "gated": True,
                "message": e.message,
                "dashboard": dashboard_summary(sector_id),
            }
        raise HTTPException(status_code=404, detail=e.message) from e
    return {"sector_id": sector_id, "gated": False, "dashboard": dashboard_summary(sector_id)}


@router.get("/hint-calibration")
def get_hint_calibration():
    """提示分校准闭环状态（F4）。"""
    return calibration_summary()


@router.get("/hint-calibration/suggest")
def get_hint_calibration_suggest():
    """基于 outcome 的透明权重调整建议。"""
    return suggest_weight_adjustments()


@router.get("/hint-outcomes")
def get_hint_outcomes(sector_id: str | None = None, outcome_status: str | None = None):
    """提示分人工裁决 outcome 回溯列表。"""
    return {"items": list_outcomes(sector_id=sector_id, outcome_status=outcome_status)}


@router.post("/hint-outcomes/{outcome_id}/resolve")
def post_resolve_hint_outcome(outcome_id: str, req: ResolveOutcomeRequest):
    try:
        row = resolve_outcome(outcome_id, req.outcome_status, req.operator)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if row is None:
        raise HTTPException(status_code=404, detail="outcome 不存在")
    return row
