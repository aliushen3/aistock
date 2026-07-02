from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ontology.action_executor import ActionError, action_executor
from app.ontology.object_store import list_sectors as ont_list_sectors

router = APIRouter(prefix="/sectors", tags=["sectors"])


class ConfirmSectorRequest(BaseModel):
    confirmed: bool
    reason: str = Field(..., min_length=5)
    operator: str = "analyst"


class BoardEntry(BaseModel):
    type: str = Field("concept", description="concept | industry")
    name: str = Field(..., min_length=1)


class ConstituentConfigRequest(BaseModel):
    boards: list[BoardEntry] = Field(default_factory=list)
    default_product_id: str | None = None
    product_keywords: dict[str, list[str]] = Field(default_factory=dict)


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


@router.get("/workflow-overview")
def sector_workflow_overview(mode: str = "fusion"):
    """全部赛道的五阶段工作流概览 — 首页驾驶舱赛道看板。"""
    from app.services.workflow_progress import get_workflow_overview

    items = get_workflow_overview(mode=mode)
    return {"items": items, "count": len(items)}


@router.get("/{sector_id}/workflow-status")
def sector_workflow_status(sector_id: str, mode: str = "fusion"):
    """工作流进度（七步引擎 + 五阶段呈现）、待办与断点续跑步骤。"""
    from app.services.graph_store import get_store
    from app.services.workflow_progress import get_sector_workflow_status

    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {sector_id}")
    try:
        return get_sector_workflow_status(sector_id, mode=mode)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{sector_id}/constituent-config")
def get_constituent_config(sector_id: str):
    from app.services.graph_store import get_store
    from app.services.sector_board_config import get_sector_board_config_meta

    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {sector_id}")
    return get_sector_board_config_meta(sector_id)


@router.put("/{sector_id}/constituent-config")
def put_constituent_config(sector_id: str, req: ConstituentConfigRequest):
    from app.services.graph_store import get_store
    from app.services.sector_board_config import save_sector_board_config

    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {sector_id}")
    try:
        return save_sector_board_config(
            sector_id,
            {
                "boards": [b.model_dump() for b in req.boards],
                "default_product_id": req.default_product_id,
                "product_keywords": req.product_keywords,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{sector_id}/constituent-config/import-seed")
def import_constituent_config_seed(sector_id: str):
    """将内置 sector_boards.json 种子导入到 Sector.attrs（一次性迁移）。"""
    from app.services.graph_store import get_store
    from app.services.sector_board_config import import_legacy_json_to_db

    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {sector_id}")
    try:
        return import_legacy_json_to_db(sector_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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
