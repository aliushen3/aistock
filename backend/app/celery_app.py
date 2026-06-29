"""Celery 应用配置。"""

from celery import Celery

from app.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    "aistock",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.tasks.knowledge_tasks", "app.tasks.data_tasks", "app.tasks.agent_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        "sync-watchlist-metrics-daily": {
            "task": "data.sync_watchlist_metrics",
            "schedule": 86400.0,
        },
        "sync-watchlist-seven-layer-daily": {
            "task": "data.sync_watchlist_seven_layer",
            "schedule": 86400.0,
        },
        "monitor-watch-hourly": {
            "task": "agents.monitor_watch",
            "schedule": 3600.0,
            "kwargs": {"sector_id": None},
        },
        "refresh-watchlist-daily": {
            "task": "agents.refresh_watchlist",
            "schedule": 86400.0,
        },
    },
)
