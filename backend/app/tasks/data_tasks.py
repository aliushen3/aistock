"""数据同步 Celery 任务 — 阶段 A。"""

from __future__ import annotations

from app.celery_app import celery_app
from app.services.graph_store import get_store
from app.services.ods_service import sync_announcements, sync_industry_metrics, sync_market_daily
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


@celery_app.task(name="data.sync_sector_bundle")
def sync_sector_bundle_task(sector_id: str = "sector_ai_compute"):
    """指标 + 行情 + 公告一次性同步。"""
    store = get_store()
    codes = list(store.companies.keys())
    m = sync_industry_metrics(sector_id)
    mk = sync_market_daily(codes)
    ann = sync_announcements(codes)
    return {"metrics": m, "market": mk, "announcements": ann}
