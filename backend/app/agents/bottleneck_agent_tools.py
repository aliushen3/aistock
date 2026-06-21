"""瓶颈哨兵 Agent 工具集。"""

from __future__ import annotations

from typing import Any

from app.ontology.object_store import get_product
from app.services.graph_store import get_store
from app.services.hint_score import calc_bottleneck_hint, load_config
from app.services.metrics import get_sector_metrics_summary
from app.services.vector_store import search_hybrid

TOOL_SPECS: list[dict] = [
    {"name": "list_sector_products", "input_schema": {"sector_id": "赛道 ID"}},
    {"name": "calc_product_hint", "input_schema": {"product_id": "产品 ID"}},
    {"name": "collect_metrics_signals", "input_schema": {"sector_id": "赛道 ID"}},
    {"name": "search_bottleneck_evidence", "input_schema": {"sector_id": "赛道 ID", "product_name": "产品名"}},
]


def tool_list_sector_products(sector_id: str) -> list[dict]:
    store = get_store()
    out = []
    for p in store.list_products(sector_id):
        merged = get_product(p["id"]) or p
        out.append(
            {
                "product_id": p["id"],
                "product_name": p["name"],
                "bottleneck_status": merged.get("bottleneck_status", "none"),
                "layer": merged.get("layer"),
            }
        )
    return out


def tool_calc_product_hint(product_id: str) -> dict:
    product = get_product(product_id)
    if not product:
        return {"error": "产品不存在"}
    result = calc_bottleneck_hint(product)
    return {
        "product_id": product_id,
        "product_name": product["name"],
        "hint_score": result.total,
        "hint_level": result.hint_level,
        "hit_rules": result.hit_rules,
        "bottleneck_status": product.get("bottleneck_status", "none"),
    }


def tool_collect_metrics_signals(sector_id: str) -> dict:
    return get_sector_metrics_summary(sector_id) or {}


def tool_search_bottleneck_evidence(sector_id: str, product_name: str, top_k: int = 3) -> list[dict]:
    store = get_store()
    query = f"{product_name} 瓶颈 产能 扩产 供不应求"
    return search_hybrid(query, list(store.evidence.values()), sector_id=sector_id, top_k=top_k)


def execute_tool(name: str, action_input: dict | None = None) -> Any:
    inp = action_input or {}
    if name == "list_sector_products":
        return tool_list_sector_products(inp["sector_id"])
    if name == "calc_product_hint":
        return tool_calc_product_hint(inp["product_id"])
    if name == "collect_metrics_signals":
        return tool_collect_metrics_signals(inp["sector_id"])
    if name == "search_bottleneck_evidence":
        return tool_search_bottleneck_evidence(inp["sector_id"], inp["product_name"])
    raise ValueError(f"未知工具: {name}")


def hint_thresholds() -> dict:
    return load_config().get("thresholds", {})
