from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.adapters.registry import list_adapters
from app.services.a_share_data_source import (
    AShareDataError,
    fetch_layer_data,
    list_seven_layer_capabilities,
    route_task_to_layers,
)
from app.services.graph_store import get_store, sector_company_codes
from app.services.graph_ingest import ontology_company_stats, sync_constituents
from app.services.ods_service import (
    ods_stats,
    sync_announcements,
    sync_external_reports,
    sync_financials,
    sync_industry_metrics,
    sync_layer_to_ods,
    sync_market_daily,
)

router = APIRouter(prefix="/data", tags=["data"])


def _require_sector_stock_codes(sector_id: str) -> list[str]:
    """按赛道取成分股代码；缺失时返回 400 与可操作的提示。"""
    store = get_store()
    codes = sector_company_codes(sector_id)
    if codes:
        return codes
    if not store.list_products(sector_id):
        raise HTTPException(
            status_code=400,
            detail="赛道尚无产业链环节（Product），请先在「知识抽取」确认拓扑后再同步数据",
        )
    raise HTTPException(
        status_code=400,
        detail="当前赛道 0 只成分股，请先配置成分股映射并执行「同步成分股」",
    )


class SevenLayerFetchRequest(BaseModel):
    layer: str
    stock_code: str | None = None
    limit: int = Field(20, ge=1, le=100)


class SevenLayerSyncRequest(BaseModel):
    layer: str
    sector_id: str


@router.get("/seven-layer/capabilities")
def get_seven_layer_capabilities():
    return {"items": list_seven_layer_capabilities(), "layer_count": 7}


@router.post("/seven-layer/fetch")
def post_seven_layer_fetch(req: SevenLayerFetchRequest):
    try:
        return fetch_layer_data(req.layer, stock_code=req.stock_code, limit=req.limit)
    except AShareDataError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/seven-layer/route/{task}")
def get_seven_layer_route(task: str):
    try:
        layers = route_task_to_layers(task)
        caps = [c for c in list_seven_layer_capabilities() if c["layer"] in layers]
        return {"task": task, "layers": layers, "capabilities": caps}
    except AShareDataError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/seven-layer/sync")
def post_seven_layer_sync(req: SevenLayerSyncRequest):
    if get_store().get_sector(req.sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")
    try:
        return sync_layer_to_ods(req.layer, req.sector_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/adapters")
def get_data_adapters():
    from app.config import (
        DATA_ADAPTER,
        DATA_ADAPTER_ANNOUNCEMENT,
        DATA_ADAPTER_CONSTITUENT,
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
            "constituent": DATA_ADAPTER_CONSTITUENT,
            "legacy": DATA_ADAPTER,
        },
    }


@router.get("/ods/stats")
def get_ods_stats():
    stats = ods_stats()
    stats["ontology_companies"] = ontology_company_stats()
    return stats


@router.post("/sync/constituents/{sector_id}")
def trigger_constituents_sync(sector_id: str, adapter: str | None = None):
    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")
    try:
        return sync_constituents(sector_id, adapter_name=adapter)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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
    codes = _require_sector_stock_codes(sector_id)
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
    codes = _require_sector_stock_codes(sector_id)
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
    codes = _require_sector_stock_codes(sector_id)
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
    codes = _require_sector_stock_codes(sector_id)
    try:
        result = sync_external_reports(codes, adapter_name=adapter)
        result["stock_codes"] = len(codes)
        return result
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
