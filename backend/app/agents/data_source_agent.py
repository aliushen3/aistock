"""数据源获取智能体 — 七层架构任务路由 + 分层拉取 + 可选 ODS 同步。"""

from __future__ import annotations

import uuid
from typing import Any

from app.agents.data_source_agent_tools import (
    TOOL_SPECS,
    tool_fetch_layer_preview,
    tool_route_task,
)
from app.services.a_share_data_source import AShareDataError, route_task_to_layers
from app.services.graph_store import get_store
from app.services.ods_service import sync_layer_to_ods


def _resolve_stock_codes(
    stock_code: str | None,
    stock_codes: list[str] | None,
    sector_id: str | None,
) -> list[str]:
    if stock_codes:
        return stock_codes
    if stock_code:
        return [stock_code]
    if sector_id:
        store = get_store()
        if store.get_sector(sector_id) is None:
            raise ValueError(f"赛道不存在: {sector_id}")
        return list(store.companies.keys())
    return []


def _fetch_layers_for_task(
    task: str,
    stock_code: str | None,
    limit: int,
) -> tuple[list[str], dict[str, Any], dict[str, str]]:
    layers = route_task_to_layers(task)
    fetched: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for layer in layers:
        try:
            fetched[layer] = tool_fetch_layer_preview(layer, stock_code=stock_code, limit=limit)
        except (AShareDataError, ValueError) as exc:
            errors[layer] = str(exc)
    return layers, fetched, errors


def _sync_ods_layers(sector_id: str, layers: list[str]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for cap in layers:
        layer = cap if isinstance(cap, str) else cap.get("layer")
        if layer not in {"market", "research", "fundamental", "announcement"}:
            continue
        try:
            results[layer] = sync_layer_to_ods(layer, sector_id)
        except Exception as exc:
            results[layer] = {"status": "error", "detail": str(exc)}
    return results


def run_data_source_agent(
    task: str,
    stock_code: str | None = None,
    stock_codes: list[str] | None = None,
    sector_id: str | None = None,
    sync_ods: bool = False,
    limit: int = 20,
    operator: str = "analyst",
) -> dict[str, Any]:
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    route = tool_route_task(task)
    primary_code = stock_code or (stock_codes[0] if stock_codes else None)
    layers, fetched, errors = _fetch_layers_for_task(task, primary_code, limit)

    ods_sync: dict[str, Any] | None = None
    if sync_ods:
        if not sector_id:
            raise ValueError("sync_ods=true 时需要 sector_id")
        ods_sync = _sync_ods_layers(sector_id, layers)

    ok_layers = [layer for layer in layers if layer not in errors]
    summary = (
        f"任务 {task}：成功拉取 {len(ok_layers)}/{len(layers)} 层"
        + (f"，ODS 同步 {len(ods_sync or {})} 层" if ods_sync else "")
    )

    return {
        "run_id": run_id,
        "agent": "data_source_fetch_v1",
        "operator": operator,
        "task": task,
        "stock_code": primary_code,
        "stock_codes": _resolve_stock_codes(stock_code, stock_codes, sector_id),
        "sector_id": sector_id,
        "layers": layers,
        "route": route,
        "fetched": fetched,
        "errors": errors,
        "ods_sync": ods_sync,
        "tools_available": [t["name"] for t in TOOL_SPECS],
        "agent_summary": summary,
        "disclaimer": "直连 HTTP 数据源仅供投研参考，东财接口已内置限流",
    }
