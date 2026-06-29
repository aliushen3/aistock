"""数据同步 Celery 任务 — 阶段 A。"""

from __future__ import annotations

from app.celery_app import celery_app
from app.services.graph_store import get_store
from app.services.graph_ingest import sync_constituents
from app.services.ods_service import (
    sync_all_ods_layers,
    sync_announcements,
    sync_external_reports,
    sync_financials,
    sync_industry_metrics,
    sync_market_daily,
)
from app.services.watchlist_service import list_watchlist_sector_ids


@celery_app.task(bind=True, name="data.sync_industry_metrics")
def sync_industry_metrics_task(self, sector_id: str = "sector_ai_compute", adapter: str | None = None):
    self.update_state(state="PROGRESS", meta={"step": "fetching_metrics"})
    return sync_industry_metrics(sector_id, adapter_name=adapter)


@celery_app.task(bind=True, name="data.sync_watchlist_metrics")
def sync_watchlist_metrics_task(self, adapter: str | None = None):
    """同步动态观察清单内全部赛道的产业指标。"""
    sector_ids = list_watchlist_sector_ids()
    results = []
    for sid in sector_ids:
        self.update_state(state="PROGRESS", meta={"step": "fetching_metrics", "sector_id": sid})
        results.append({"sector_id": sid, **sync_industry_metrics(sid, adapter_name=adapter)})
    return {"sector_count": len(results), "results": results}


@celery_app.task(bind=True, name="data.sync_market_daily")
def sync_market_daily_task(self, sector_id: str = "sector_ai_compute", adapter: str | None = None):
    store = get_store()
    codes = list(store.companies.keys())
    self.update_state(state="PROGRESS", meta={"step": "fetching_market", "count": len(codes)})
    return sync_market_daily(codes, adapter_name=adapter)


@celery_app.task(bind=True, name="data.sync_announcements")
def sync_announcements_task(self, sector_id: str = "sector_ai_compute", adapter: str | None = None):
    store = get_store()
    codes = list(store.companies.keys())
    self.update_state(state="PROGRESS", meta={"step": "fetching_announcements", "count": len(codes)})
    return sync_announcements(codes, adapter_name=adapter)


@celery_app.task(bind=True, name="data.sync_financials")
def sync_financials_task(self, sector_id: str = "sector_ai_compute", adapter: str | None = None):
    store = get_store()
    codes = list(store.companies.keys())
    self.update_state(state="PROGRESS", meta={"step": "fetching_financials", "count": len(codes)})
    return sync_financials(codes, adapter_name=adapter)


@celery_app.task(bind=True, name="data.sync_external_reports")
def sync_external_reports_task(self, sector_id: str = "sector_ai_compute", adapter: str | None = None):
    store = get_store()
    codes = list(store.companies.keys())
    self.update_state(state="PROGRESS", meta={"step": "fetching_reports", "count": len(codes)})
    return sync_external_reports(codes, adapter_name=adapter)


@celery_app.task(bind=True, name="data.ingest_reports_to_draft")
def ingest_reports_to_draft_task(self, sector_id: str = "sector_ai_compute"):
    """研报标题 → 知识抽取草案（产能/扩产瓶颈信号）。"""
    from app.services.report_ingest_bridge import ingest_external_reports_to_draft

    self.update_state(state="PROGRESS", meta={"step": "ingesting_reports", "sector_id": sector_id})
    return ingest_external_reports_to_draft(sector_id)


@celery_app.task(bind=True, name="data.sync_constituents")
def sync_constituents_task(self, sector_id: str = "sector_ai_compute", adapter: str | None = None):
    self.update_state(state="PROGRESS", meta={"step": "fetching_constituents", "sector_id": sector_id})
    return sync_constituents(sector_id, adapter_name=adapter)


@celery_app.task(name="data.sync_sector_bundle")
def sync_sector_bundle_task(sector_id: str = "sector_ai_compute"):
    """成分股 + 指标 + 行情 + 公告 + 财报 + 研报一次性同步。"""
    store = get_store()
    codes = list(store.companies.keys())
    con = sync_constituents(sector_id)
    store = get_store()
    codes = list(store.companies.keys())
    m = sync_industry_metrics(sector_id)
    mk = sync_market_daily(codes)
    ann = sync_announcements(codes)
    fin = sync_financials(codes)
    rep = sync_external_reports(codes)
    return {
        "constituents": con,
        "metrics": m,
        "market": mk,
        "announcements": ann,
        "financials": fin,
        "external_reports": rep,
    }


@celery_app.task(bind=True, name="data.sync_sector_seven_layer")
def sync_sector_seven_layer_task(self, sector_id: str = "sector_ai_compute"):
    """七层 ODS 就绪层（行情/研报/财报/公告）直连同步入库。"""
    self.update_state(state="PROGRESS", meta={"step": "seven_layer_sync", "sector_id": sector_id})
    return sync_all_ods_layers(sector_id)


@celery_app.task(bind=True, name="data.sync_watchlist_seven_layer")
def sync_watchlist_seven_layer_task(self):
    """对动态观察清单内全部赛道执行七层 ODS 同步（无人值守定时采集入口）。"""
    sector_ids = list_watchlist_sector_ids()
    results = []
    for sid in sector_ids:
        self.update_state(state="PROGRESS", meta={"step": "seven_layer_sync", "sector_id": sid})
        try:
            results.append({"sector_id": sid, **sync_all_ods_layers(sid)})
        except Exception as exc:  # 单赛道失败不阻断整体采集
            results.append({"sector_id": sid, "status": "error", "detail": str(exc)})
    return {"sector_count": len(results), "results": results}
