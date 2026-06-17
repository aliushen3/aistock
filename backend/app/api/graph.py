from fastapi import APIRouter, Query

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/sector/{sector_id}")
def get_sector_graph(sector_id: str, hops: int = Query(default=3, le=5)):
    """获取赛道产业链子图，供 G6 可视化。"""
    return {
        "sector_id": sector_id,
        "hops": hops,
        "nodes": [],
        "edges": [],
        "note": "一期种子数据待导入 Neo4j",
    }


@router.get("/product/{product_id}/hint-score")
def get_product_hint_score(product_id: str):
    """获取产品瓶颈提示分（非投资决策分）。"""
    return {
        "product_id": product_id,
        "hint_score": None,
        "hint_level": None,
        "status": "bottleneck_hint",
        "human_confirmed": False,
        "note": "提示分仅供排序参考，需研究员确认 bottleneck_confirmed",
    }
