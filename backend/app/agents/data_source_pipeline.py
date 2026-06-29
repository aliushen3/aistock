"""A 股七层数据源采集 Pipeline — 可编排多任务 + ODS 同步。"""

from __future__ import annotations

import uuid
from typing import Any

from app.agents.data_source_agent import run_data_source_agent
from app.services.graph_store import get_store
from app.services.ods_service import sync_all_ods_layers

DATA_SOURCE_PIPELINE_PRESETS: dict[str, dict[str, Any]] = {
    "sector_scan": {
        "label": "赛道信号扫描",
        "description": "信号层 + 研报 + 新闻预览（不落库）",
        "tasks": ["sector_scan"],
        "sync_ods": False,
    },
    "ods_warmup": {
        "label": "ODS 四层入库",
        "description": "行情/研报/财报/公告直连同步至 ODS",
        "tasks": [],
        "sync_ods": True,
    },
    "full_collection": {
        "label": "全量采集",
        "description": "赛道扫描预览 → ODS 四层入库",
        "tasks": ["sector_scan", "research"],
        "sync_ods": True,
    },
    "valuation_pass": {
        "label": "估值巡检",
        "description": "成分股估值快照（market+research+fundamental）",
        "tasks": ["valuation"],
        "sync_ods": False,
    },
}

ORCHESTRATOR_DATA_COLLECTION_STEPS = [
    "sector_bootstrap",
    "data_source_fetch",
    "data_source_ods_sync",
]


def list_data_source_pipeline_presets() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key, spec in DATA_SOURCE_PIPELINE_PRESETS.items():
        items.append({"preset": key, **spec})
    items.append(
        {
            "preset": "orchestrator_data_collection",
            "label": "Orchestrator 数据采集链",
            "description": "冷启动 → 七层预览 → ODS 四层同步",
            "steps": ORCHESTRATOR_DATA_COLLECTION_STEPS,
        }
    )
    return items


def run_data_source_pipeline(
    sector_id: str,
    *,
    tasks: list[str] | None = None,
    preset: str | None = None,
    sync_ods: bool | None = None,
    stock_code: str | None = None,
    limit: int = 20,
    operator: str = "analyst",
    stop_on_error: bool = False,
) -> dict[str, Any]:
    """按序执行多个 data_source 任务，可选末尾 ODS 全层同步。"""
    if get_store().get_sector(sector_id) is None:
        raise ValueError(f"赛道不存在: {sector_id}")

    if preset:
        spec = DATA_SOURCE_PIPELINE_PRESETS.get(preset)
        if spec is None:
            raise ValueError(f"未知 preset: {preset}")
        task_list = list(spec.get("tasks") or [])
        if sync_ods is None:
            sync_ods = bool(spec.get("sync_ods"))
    else:
        task_list = list(tasks or ["sector_scan"])
        if sync_ods is None:
            sync_ods = False

    pipeline_id = f"pipe_{uuid.uuid4().hex[:12]}"
    steps: list[dict[str, Any]] = []

    for task in task_list:
        try:
            output = run_data_source_agent(
                task=task,
                stock_code=stock_code,
                sector_id=sector_id,
                sync_ods=False,
                limit=limit,
                operator=operator,
            )
            status = "ok" if not output.get("errors") else "partial"
            steps.append({"step": task, "status": status, "output": output})
            if stop_on_error and output.get("errors"):
                break
        except Exception as exc:
            steps.append({"step": task, "status": "error", "error": str(exc)})
            if stop_on_error:
                break

    ods_output: dict[str, Any] | None = None
    if sync_ods:
        try:
            ods_output = sync_all_ods_layers(sector_id)
            steps.append({"step": "ods_sync", "status": ods_output.get("status", "ok"), "output": ods_output})
        except Exception as exc:
            steps.append({"step": "ods_sync", "status": "error", "error": str(exc)})

    completed = sum(1 for s in steps if s.get("status") in ("ok", "partial", "skipped"))
    return {
        "pipeline_id": pipeline_id,
        "agent": "data_source_pipeline_v1",
        "sector_id": sector_id,
        "preset": preset,
        "tasks": task_list,
        "sync_ods": bool(sync_ods),
        "steps_requested": len(task_list) + (1 if sync_ods else 0),
        "steps_completed": completed,
        "results": steps,
        "agent_summary": (
            f"Pipeline 完成 {completed}/{len(steps)} 步"
            + (f"（preset={preset}）" if preset else "")
        ),
        "disclaimer": "直连 HTTP 数据源仅供投研参考，ODS 同步需 PostgreSQL 启用",
    }
