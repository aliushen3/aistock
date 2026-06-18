from enum import Enum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import report as report_service
from app.services.audit import audit_log
from app.services.graph_store import get_store
from app.services.serenity_trace import serenity_reverse_trace

router = APIRouter(prefix="/reasoning", tags=["reasoning"])


class ReasoningMode(str, Enum):
    BUY_SIDE = "buy_side"
    SERENITY = "serenity"
    FUSION = "fusion"


class GraphRAGRequest(BaseModel):
    sector_id: str
    mode: ReasoningMode = ReasoningMode.FUSION


class ReviewRequest(BaseModel):
    action: str  # approve / reject / revise
    comments: str = ""
    operator: str = "analyst"


@router.post("/graphrag")
def run_graphrag(req: GraphRAGRequest):
    """生成投研逻辑草稿；status 恒为 draft，需审核后发布。"""
    store = get_store()
    if store.get_sector(req.sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {req.sector_id}")
    return report_service.generate_report(store, req.sector_id, req.mode.value)


@router.get("/serenity/trace")
def serenity_trace(sector_id: str):
    """Serenity 逆向溯源路径（供图谱高亮展示）。"""
    store = get_store()
    sector = store.get_sector(sector_id)
    if sector is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {sector_id}")
    paths = serenity_reverse_trace(store, sector.get("terminal_products", []), sector_id)
    return {
        "sector_id": sector_id,
        "count": len(paths),
        "paths": [
            {
                "path_id": p.path_id,
                "node_ids": p.node_ids,
                "node_names": p.node_names,
                "niche_product_id": p.niche_product_id,
                "niche_product_name": p.niche_product_name,
                "hop_count": p.hop_count,
                "serenity_hint": p.serenity_hint,
                "companies": p.companies,
                "prune_reasons": p.prune_reasons,
                "status": p.status,
            }
            for p in paths
        ],
    }


@router.get("/reports/{report_id}")
def get_report(report_id: str):
    report = report_service.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"报告不存在: {report_id}")
    return report


@router.post("/reports/{report_id}/review")
def review_report(report_id: str, req: ReviewRequest):
    """研究员审核报告：approve / reject / revise（报告发布门控）。"""
    report = report_service.review_report(report_id, req.action, req.comments)
    if report is None:
        raise HTTPException(status_code=404, detail=f"报告不存在: {report_id}")
    audit_log.record(
        action="review_report",
        operator=req.operator,
        target=report_id,
        detail={"action": req.action, "comments": req.comments},
    )
    return {"report_id": report_id, "action": req.action, "new_status": report["status"]}
