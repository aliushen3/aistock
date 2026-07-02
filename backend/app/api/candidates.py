from enum import Enum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ontology.action_executor import ActionError, action_executor
from app.ontology.object_store import make_candidate_entry_id
from app.services.audit import audit_log
from app.services.candidate_pool import build_pool
from app.services.graph_store import get_store
from app.services.workflow import WorkflowGateError, require_sector_confirmed

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
    # 三道闸复核确认：预期透支/价值不可捕获时必须显式确认（后端硬校验，见 action_executor）
    gate_ack: bool = False


@router.get("")
def list_candidates(sector_id: str, mode: PoolMode = PoolMode.FUSION):
    """获取候选池；默认均为 pending，需人工确认入池。"""
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {sector_id}")
    gated = False
    gate_message = None
    try:
        require_sector_confirmed(sector_id)
    except WorkflowGateError as e:
        gated = True
        gate_message = e.message
    items = build_pool(store, sector_id, mode.value)
    return {
        "sector_id": sector_id,
        "mode": mode,
        "count": len(items),
        "items": items,
        "gated": gated,
        "gate_message": gate_message,
        "note": "所有候选 status=pending，须调用 /confirm 后方可入正式池；提示分不构成投资建议",
    }


@router.get("/dossier")
def candidate_dossier(sector_id: str, stock_code: str, mode: PoolMode = PoolMode.FUSION):
    """标的论证档案 — 单标的多空对照 + 三道闸依据（供论证工作台）。"""
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {sector_id}")

    items = build_pool(store, sector_id, mode.value)
    candidate = next((i for i in items if i["stock_code"] == stock_code), None)
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"候选标的不存在: {stock_code}")

    from app.services.bearcase_store import list_bear_cases
    from app.services.diagnosis import diagnose_company
    from app.services.report import latest_sector_report

    bears = list_bear_cases(sector_id=sector_id, stock_code=stock_code)

    diagnosis = None
    try:
        diagnosis = diagnose_company(store, sector_id, stock_code)
    except Exception:
        diagnosis = None

    bull = None
    report = latest_sector_report(sector_id)
    if report:
        thesis = next(
            (c for c in report.get("candidates", []) if c.get("stock_code") == stock_code),
            None,
        )
        bull = {
            "report_id": report.get("report_id"),
            "report_status": report.get("status"),
            "thesis_summary": (thesis or {}).get("thesis_summary"),
            "logic_chain": report.get("logic_chain", []),
            "citations": report.get("citations", []),
        }

    return {
        "sector_id": sector_id,
        "mode": mode,
        "candidate": candidate,
        "bull": bull,
        "bear_cases": bears,
        "diagnosis": diagnosis,
        "note": "多空并排等强展示；高severity空头未回应将阻断入池（闸三）",
    }


@router.post("/confirm")
def confirm_candidates(req: ConfirmPoolRequest):
    """研究员/基金经理确认入池或否决 — 委托 Ontology Action 执行。"""
    store = get_store()
    if store.get_sector(req.sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {req.sector_id}")
    try:
        require_sector_confirmed(req.sector_id)
    except WorkflowGateError as e:
        raise HTTPException(status_code=403, detail={"code": e.code, "message": e.message}) from e

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
                params={"reason": req.reason, "gate_ack": req.gate_ack},
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
