from fastapi import APIRouter, HTTPException

from app.adapters.registry import get_adapter, list_adapters
from app.services.graph_store import get_store
from app.services.ods_service import ods_stats, sync_announcements, sync_industry_metrics, sync_market_daily

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/adapters")
def get_data_adapters():
    return {"items": list_adapters(), "default": __import__("app.config", fromlist=["DATA_ADAPTER"]).DATA_ADAPTER}


@router.get("/ods/stats")
def get_ods_stats():
    return ods_stats()


@router.post("/sync/metrics/{sector_id}")
def trigger_metrics_sync(sector_id: str, adapter: str | None = None):
    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")
    try:
        return sync_industry_metrics(sector_id, adapter_name=adapter)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sync/market/{sector_id}")
def trigger_market_sync(sector_id: str, adapter: str | None = None):
    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")
    store = get_store()
    codes = list(store.companies.keys())
    try:
        return sync_market_daily(codes, adapter_name=adapter)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e


@router.post("/sync/announcements/{sector_id}")
def trigger_announcements_sync(sector_id: str, adapter: str | None = None):
    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")
    store = get_store()
    codes = list(store.companies.keys())
    try:
        return sync_announcements(codes, adapter_name=adapter)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
