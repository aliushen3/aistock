from fastapi import APIRouter, HTTPException

from app.services.diagnosis import diagnose_company, diagnose_sector
from app.services.graph_store import get_store
from app.services.workflow import WorkflowGateError, require_sector_confirmed

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


@router.get("/sector/{sector_id}")
def sector_diagnosis(sector_id: str):
    """赛道内全部关联公司诊断。"""
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")
    try:
        require_sector_confirmed(sector_id)
    except WorkflowGateError as e:
        if e.code != "sector_not_confirmed":
            raise HTTPException(status_code=404, detail=e.message) from e
    items = diagnose_sector(store, sector_id)
    return {"sector_id": sector_id, "count": len(items), "items": items}


@router.get("/company/{stock_code}")
def company_diagnosis(stock_code: str, sector_id: str = "sector_ai_compute"):
    store = get_store()
    try:
        result = diagnose_company(store, sector_id, stock_code)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return result
