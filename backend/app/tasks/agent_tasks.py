"""Agent 相关 Celery 任务 — 阶段 C。"""

from __future__ import annotations

from app.agents.monitor_watch_agent import run_monitor_watch_agent
from app.celery_app import celery_app
from app.services.watchlist_service import list_watchlist_sector_ids


@celery_app.task(name="agents.monitor_watch")
def monitor_watch_task(sector_id: str | None = None):
    """扫描动态观察清单内全部赛道（sector_id 为空时）。"""
    if sector_id:
        return run_monitor_watch_agent(sector_id=sector_id)
    summaries = []
    for sid in list_watchlist_sector_ids():
        summaries.append(run_monitor_watch_agent(sector_id=sid))
    return {
        "sectors_scanned": len(summaries),
        "results": summaries,
    }


@celery_app.task(name="agents.refresh_watchlist")
def refresh_watchlist_task(focus: str | None = None):
    from app.services.watchlist_service import build_dynamic_watchlist

    return build_dynamic_watchlist(focus=focus, refresh=True)
