"""Ontology 语义层 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ontology.action_executor import ActionError, action_executor
from app.ontology.function_runtime import function_runtime
from app.ontology.object_store import (
    get_candidate_entry,
    get_product,
    get_research_report,
    get_sector,
    make_candidate_entry_id,
    query_object_set as run_object_set_query,
)
from app.ontology.registry import ontology_registry

router = APIRouter(prefix="/ontology", tags=["ontology"])


class ActionExecuteRequest(BaseModel):
    target: dict[str, str] = Field(..., description='{"type": "CandidatePoolEntry", "id": "..."}')
    params: dict[str, Any] = Field(default_factory=dict)
    operator: str = "analyst"


class BatchPoolActionRequest(BaseModel):
    sector_id: str
    mode: str = "fusion"
    stock_codes: list[str]
    reason: str = Field(..., min_length=5)
    operator: str = "analyst"
    gate_ack: bool = False


class FunctionInvokeRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


@router.get("/registry/action-types")
def list_action_types():
    """供前端动态渲染 Action 表单。"""
    return {
        "version": ontology_registry.version,
        "items": ontology_registry.list_action_types_summary(),
    }


@router.get("/registry/object-types")
def list_object_types():
    return {
        "version": ontology_registry.version,
        "items": [
            {"name": k, "display_name": v.get("display_name", k), "primary_key": v.get("primary_key")}
            for k, v in ontology_registry.object_types.items()
        ],
    }


@router.get("/registry/functions")
def list_functions():
    return {"version": ontology_registry.version, "items": function_runtime.list_functions()}


@router.get("/objects/{object_type}/{object_id}")
def get_object(object_type: str, object_id: str):
    if object_type == "Sector":
        obj = get_sector(object_id)
    elif object_type == "Product":
        obj = get_product(object_id)
    elif object_type == "CandidatePoolEntry":
        obj = get_candidate_entry(object_id)
    elif object_type == "ResearchReport":
        obj = get_research_report(object_id)
    else:
        raise HTTPException(status_code=400, detail=f"不支持的对象类型: {object_type}")
    if obj is None:
        raise HTTPException(status_code=404, detail="对象不存在")
    return {"object_type": object_type, "object_id": object_id, "data": obj}


@router.get("/object-sets/{set_name}")
def get_object_set_endpoint(set_name: str, sector_id: str = "sector_ai_compute", mode: str = "fusion"):
    try:
        items = run_object_set_query(
            set_name, filter_extra={"sector_id": sector_id, "mode": mode}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"object_set": set_name, "count": len(items), "items": items}


@router.get("/pending-reviews")
def list_pending_reviews():
    from app.services.dual_review import list_pending

    return {"items": list_pending()}


@router.post("/pending-reviews/{pending_id}/approve")
def approve_pending_review(pending_id: str, operator: str = "fund_manager"):
    """第二人复核通过 — 以存档参数重放原 Action，effects 正式生效。"""
    from app.services.dual_review import get_pending

    pending = get_pending(pending_id)
    if pending is None or pending.get("status") != "pending":
        raise HTTPException(status_code=404, detail="待复核记录不存在或已处理")
    try:
        result = action_executor.execute_with_params(
            action_type=pending["action_type"],
            target_type=pending["target_type"],
            target_id=pending["target_id"],
            params=pending.get("params") or {},
            operator=operator,
        )
    except ActionError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message}) from e
    return {
        "pending_id": pending_id,
        "status": result.status,
        "audit_id": result.audit_id,
        "message": result.message,
    }


@router.post("/pending-reviews/{pending_id}/reject")
def reject_pending_review(pending_id: str, operator: str = "fund_manager", reason: str = ""):
    """第二人复核驳回 — 原 Action 不生效，留痕审计。"""
    from app.services.audit import audit_log
    from app.services.dual_review import reject_pending

    try:
        pending = reject_pending(pending_id, operator, reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if pending is None:
        raise HTTPException(status_code=404, detail="待复核记录不存在或已处理")
    audit_log.record(
        action=f"ontology.{pending['action_type']}.review_rejected",
        operator=operator,
        target=f"{pending['target_type']}:{pending['target_id']}",
        detail={"pending_id": pending_id, "reason": reason},
    )
    return {"pending_id": pending_id, "status": "rejected", "reason": reason}


@router.post("/actions/{action_type}/execute")
def execute_action(action_type: str, req: ActionExecuteRequest):
    """执行单个 Ontology Action。"""
    target_type = req.target.get("type")
    target_id = req.target.get("id")
    if not target_type or not target_id:
        raise HTTPException(status_code=400, detail="target 需包含 type 与 id")
    try:
        result = action_executor.execute_with_params(
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            params=req.params,
            operator=req.operator,
        )
    except ActionError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message}) from e
    return {
        "action_type": result.action_type,
        "target": {"type": result.target_type, "id": result.target_id},
        "status": result.status,
        "audit_id": result.audit_id,
        "requires_dual_review": result.requires_dual_review,
        "pending_id": result.pending_id,
        "message": result.message,
    }


@router.post("/actions/{action_type}/batch-pool")
def batch_pool_action(action_type: str, req: BatchPoolActionRequest):
    """批量对候选池执行 ApprovePoolEntry / RejectPoolEntry。"""
    if action_type not in ("ApprovePoolEntry", "RejectPoolEntry"):
        raise HTTPException(status_code=400, detail="batch-pool 仅支持 ApprovePoolEntry / RejectPoolEntry")
    results = []
    errors = []
    for code in req.stock_codes:
        entry_id = make_candidate_entry_id(req.sector_id, req.mode, code)
        try:
            r = action_executor.execute_with_params(
                action_type=action_type,
                target_type="CandidatePoolEntry",
                target_id=entry_id,
                params={"reason": req.reason, "gate_ack": req.gate_ack},
                operator=req.operator,
            )
            results.append({"stock_code": code, "audit_id": r.audit_id, "status": "ok"})
        except ActionError as e:
            errors.append({"stock_code": code, "error": e.message})
    if errors and not results:
        raise HTTPException(status_code=400, detail={"errors": errors})
    return {
        "action_type": action_type,
        "processed": len(results),
        "results": results,
        "errors": errors,
        "message": f"已处理 {len(results)} 个标的",
    }


@router.post("/functions/{function_name}/invoke")
def invoke_function(function_name: str, req: FunctionInvokeRequest):
    try:
        output = function_runtime.invoke(function_name, req.inputs)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    spec = ontology_registry.get_function(function_name) or {}
    return {
        "function": function_name,
        "output": output,
        "disclaimer": spec.get("disclaimer"),
    }
