"""数据源获取智能体工具集 — 七层架构 A 股直连 HTTP 能力。"""

from __future__ import annotations

from typing import Any

from app.services.a_share_data_source import (
    SEVEN_LAYER_CAPABILITIES,
    compute_valuation_snapshot,
    fetch_layer_data,
    list_seven_layer_capabilities,
    route_task_to_layers,
)
from app.services.graph_store import get_store
from app.services.ods_service import sync_layer_to_ods

TOOL_SPECS: list[dict] = [
    {
        "name": "list_seven_layer_capabilities",
        "description": "列出 A 股七层数据架构能力（层、数据源、操作、ODS 就绪）",
        "input_schema": {},
    },
    {
        "name": "route_task_to_layers",
        "description": "按任务类型映射需要拉取的七层",
        "input_schema": {"task": "valuation|quote|research|signal|news|fundamental|announcement|sector_scan"},
    },
    {
        "name": "fetch_layer_preview",
        "description": "预览指定层数据（直连 HTTP，不落库）",
        "input_schema": {
            "layer": "market|research|signal|capital|news|fundamental|announcement",
            "stock_code": "可选，news/signal 层可无",
            "limit": "默认 20",
        },
    },
    {
        "name": "compute_valuation",
        "description": "腾讯行情 + 东财研报一致预期 → 估值快照",
        "input_schema": {"stock_code": "6 位 A 股代码"},
    },
    {
        "name": "sync_ods_for_layer",
        "description": "将 ODS 就绪层数据同步入库（需 sector_id）",
        "input_schema": {
            "layer": "market|research|fundamental|announcement",
            "sector_id": "赛道 ID",
        },
    },
]


def tool_list_capabilities() -> list[dict[str, Any]]:
    return list_seven_layer_capabilities()


def tool_route_task(task: str) -> dict[str, Any]:
    layers = route_task_to_layers(task)
    matched = [c for c in SEVEN_LAYER_CAPABILITIES if c["layer"] in layers]
    return {"task": task, "layers": layers, "capabilities": matched}


def tool_fetch_layer_preview(layer: str, stock_code: str | None = None, limit: int = 20) -> dict[str, Any]:
    return fetch_layer_data(layer, stock_code=stock_code, limit=limit)


def tool_compute_valuation(stock_code: str) -> dict[str, Any]:
    return compute_valuation_snapshot(stock_code)


def tool_sync_ods_for_layer(layer: str, sector_id: str) -> dict[str, Any]:
    if get_store().get_sector(sector_id) is None:
        raise ValueError(f"赛道不存在: {sector_id}")
    return sync_layer_to_ods(layer, sector_id)


def execute_tool(name: str, action_input: dict[str, Any]) -> Any:
    if name == "list_seven_layer_capabilities":
        return tool_list_capabilities()
    if name == "route_task_to_layers":
        return tool_route_task(str(action_input.get("task") or ""))
    if name == "fetch_layer_preview":
        return tool_fetch_layer_preview(
            str(action_input.get("layer") or ""),
            stock_code=action_input.get("stock_code"),
            limit=int(action_input.get("limit") or 20),
        )
    if name == "compute_valuation":
        return tool_compute_valuation(str(action_input.get("stock_code") or ""))
    if name == "sync_ods_for_layer":
        return tool_sync_ods_for_layer(
            str(action_input.get("layer") or ""),
            str(action_input.get("sector_id") or ""),
        )
    raise ValueError(f"未知工具: {name}")
