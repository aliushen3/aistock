from fastapi import APIRouter, HTTPException

from app.adapters.registry import list_adapters
from app.services.graph_store import get_store
from app.services.ods_service import (
    ods_stats,
    sync_announcements,
    sync_external_reports,
    sync_financials,
    sync_industry_metrics,
    sync_market_daily,
)

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/adapters")
def get_data_adapters():
    from app.config import (
        DATA_ADAPTER,
        DATA_ADAPTER_ANNOUNCEMENT,
        DATA_ADAPTER_FINANCIAL,
        DATA_ADAPTER_MARKET,
        DATA_ADAPTER_METRICS,
        DATA_ADAPTER_RESEARCH,
    )

    return {
        "items": list_adapters(),
        "default": DATA_ADAPTER,
        "defaults": {
            "market": DATA_ADAPTER_MARKET,
            "announcement": DATA_ADAPTER_ANNOUNCEMENT,
            "metrics": DATA_ADAPTER_METRICS,
            "financial": DATA_ADAPTER_FINANCIAL,
            "research": DATA_ADAPTER_RESEARCH,
            "legacy": DATA_ADAPTER,
        },
    }


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


@router.post("/sync/financials/{sector_id}")
def trigger_financials_sync(sector_id: str, adapter: str | None = None):
    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")
    store = get_store()
    codes = list(store.companies.keys())
    try:
        return sync_financials(codes, adapter_name=adapter)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e


@router.post("/sync/reports/{sector_id}")
def trigger_reports_sync(sector_id: str, adapter: str | None = None):
    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")
    store = get_store()
    codes = list(store.companies.keys())
    try:
        return sync_external_reports(codes, adapter_name=adapter)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e


@router.post("/reports/{sector_id}/ingest")
def trigger_reports_ingest(sector_id: str):
    """研报标题 → 知识抽取草案（产能/扩产瓶颈信号）。"""
    from app.services.report_ingest_bridge import ingest_external_reports_to_draft

    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")
    try:
        return ingest_external_reports_to_draft(sector_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
