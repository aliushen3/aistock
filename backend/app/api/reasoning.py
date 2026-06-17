from enum import Enum

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/reasoning", tags=["reasoning"])


class ReasoningMode(str, Enum):
    BUY_SIDE = "buy_side"
    SERENITY = "serenity"
    FUSION = "fusion"


class GraphRAGRequest(BaseModel):
    sector_id: str
    mode: ReasoningMode = ReasoningMode.FUSION
    product_ids: list[str] = []
    stock_codes: list[str] = []


@router.post("/graphrag")
def run_graphrag(req: GraphRAGRequest):
    """生成投研逻辑草稿；status 恒为 draft，需审核后发布。"""
    return {
        "status": "draft",
        "sector_id": req.sector_id,
        "mode": req.mode,
        "logic_chain": [],
        "counter_arguments": [],
        "unverified_claims": [],
        "note": "GraphRAG 流水线待接入 LLM + 图谱 + 向量检索",
    }


@router.post("/reports/{report_id}/review")
def review_report(report_id: str, action: str, comments: str = ""):
    """研究员审核报告：approve / reject / revise。"""
    return {
        "report_id": report_id,
        "action": action,
        "comments": comments,
        "new_status": "published" if action == "approve" else "draft",
    }
