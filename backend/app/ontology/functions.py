"""Ontology Function 实现 — 桥接现有 services 模块。"""

from __future__ import annotations

from app.ontology.object_store import get_product, get_sector
from app.services.candidate_pool import build_pool
from app.services.graph_store import get_store
from app.services.hint_score import calc_bottleneck_hint
from app.services.report import generate_report
from app.services.serenity_trace import serenity_reverse_trace


def fn_calc_bottleneck_hint(product_id: str) -> dict:
    product = get_product(product_id)
    if product is None:
        raise ValueError(f"产品不存在: {product_id}")
    result = calc_bottleneck_hint(product)
    return {
        "product_id": product_id,
        "product_name": product.get("name"),
        "hint_score": result.total,
        "hint_level": result.hint_level,
        "breakdown": {
            "supply_rigidity": result.supply_rigidity,
            "tech_barrier": result.tech_barrier,
            "supply_demand_gap": result.supply_demand_gap,
            "concentration": result.concentration,
        },
        "hit_rules": result.hit_rules,
        "disclaimer": "本分数为辅助排序提示，不构成投资建议",
    }


def fn_serenity_reverse_trace(sector_id: str) -> list[dict]:
    store = get_store()
    sector = get_sector(sector_id)
    if sector is None:
        raise ValueError(f"赛道不存在: {sector_id}")
    terminals = sector.get("terminal_products", [])
    paths = serenity_reverse_trace(store, terminals, sector_id)
    return [
        {
            "path_id": p.path_id,
            "niche_product_id": p.niche_product_id,
            "niche_product_name": p.niche_product_name,
            "hop_count": p.hop_count,
            "serenity_hint": p.serenity_hint,
            "node_names": p.node_names,
            "companies": p.companies,
        }
        for p in paths
    ]


def fn_build_fusion_pool(sector_id: str, mode: str = "fusion") -> list[dict]:
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise ValueError(f"赛道不存在: {sector_id}")
    return build_pool(store, sector_id, mode)


def fn_generate_report_draft(sector_id: str, mode: str = "fusion") -> dict:
    return generate_report(get_store(), sector_id, mode)


FUNCTION_MAP = {
    "calcBottleneckHint": fn_calc_bottleneck_hint,
    "serenityReverseTrace": fn_serenity_reverse_trace,
    "buildFusionPool": fn_build_fusion_pool,
    "generateReportDraft": fn_generate_report_draft,
}
