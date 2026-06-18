from fastapi import APIRouter, HTTPException, Query

from app.ontology.object_store import get_product
from app.services.graph_store import get_store
from app.services.hint_score import calc_bottleneck_hint

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/sector/{sector_id}")
def get_sector_graph(sector_id: str, hops: int = Query(default=3, le=5)):
    """获取赛道产业链子图，供 G6 可视化。产品节点附带瓶颈提示分。"""
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail=f"赛道不存在: {sector_id}")
    graph = store.sector_subgraph(sector_id)
    for node in graph["nodes"]:
        if node["type"] == "product":
            product = get_product(node["id"])
            if not product:
                continue
            result = calc_bottleneck_hint(product)
            node["hint_score"] = result.total
            node["hint_level"] = result.hint_level
            node["bottleneck_status"] = product.get("bottleneck_status")
    graph["note"] = "提示分仅供排序参考，瓶颈确认需研究员人工裁定"
    return graph


@router.get("/product/{product_id}/hint-score")
def get_product_hint_score(product_id: str):
    """获取产品瓶颈提示分（非投资决策分）。"""
    store = get_store()
    product = get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"产品不存在: {product_id}")
    result = calc_bottleneck_hint(product)
    return {
        "product_id": product_id,
        "product_name": product["name"],
        "hint_score": result.total,
        "hint_level": result.hint_level,
        "breakdown": {
            "supply_rigidity": result.supply_rigidity,
            "tech_barrier": result.tech_barrier,
            "supply_demand_gap": result.supply_demand_gap,
            "concentration": result.concentration,
        },
        "hit_rules": result.hit_rules,
        "bottleneck_status": product.get("bottleneck_status", "none"),
        "human_confirmed": product.get("bottleneck_status") == "bottleneck_confirmed",
        "evidence": store.resolve_evidence(result.provenance_ids),
        "note": "提示分仅供排序参考，需研究员确认 bottleneck_confirmed",
    }
