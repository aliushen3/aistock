"""Object Set 告警 — 三期监控看板数据源。"""

from __future__ import annotations

from app.ontology.object_store import get_product, get_sector, query_object_set
from app.services.graph_store import get_store
from app.services.sector_recommendations import list_recommendations
from app.services.workflow import is_sector_confirmed


def push_sector_recommendation_alerts(
    recommendations: list[dict], run_id: str
) -> list[dict]:
    """Agent 运行后将新推荐写入告警队列（内存，供 evaluate 读取）。"""
    global _recent_rec_alerts
    items = []
    for rec in recommendations:
        item = {
            "level": "high" if rec.get("beta_score", 0) >= 0.7 else "medium",
            "type": "sector_recommendation",
            "message": f"智能体推荐赛道「{rec['sector_name']}」Beta {int(rec.get('beta_score', 0)*100)}%",
            "action": "AdoptSectorRecommendation",
            "rec_id": rec["rec_id"],
            "run_id": run_id,
            "sector_name": rec["sector_name"],
            "is_new": rec.get("is_new", True),
            "beta_score": rec.get("beta_score"),
        }
        items.append(item)
    _recent_rec_alerts = items
    return items


_recent_bottleneck_alerts: list[dict] = []


def push_bottleneck_recommendation_alerts(
    recommendations: list[dict], run_id: str
) -> list[dict]:
    global _recent_bottleneck_alerts
    items = []
    for rec in recommendations:
        items.append(
            {
                "level": "high" if rec.get("hint_level") == "hint_high" else "medium",
                "type": "bottleneck_recommendation",
                "message": f"瓶颈提案「{rec['product_name']}」提示分 {rec.get('hint_score')}",
                "action": "ConfirmBottleneck",
                "rec_id": rec["rec_id"],
                "run_id": run_id,
                "product_id": rec["product_id"],
            }
        )
    _recent_bottleneck_alerts = items
    return items


def push_serenity_recommendation_alerts(
    recommendations: list[dict], run_id: str
) -> list[dict]:
    global _recent_serenity_alerts
    items = []
    for rec in recommendations:
        items.append(
            {
                "level": "high" if rec.get("serenity_hint", 0) >= 70 else "medium",
                "type": "serenity_recommendation",
                "message": f"Serenity 路径「{rec['niche_product_name']}」提示分 {rec.get('serenity_hint')}",
                "action": "ConfirmSerenityNiche",
                "rec_id": rec["rec_id"],
                "run_id": run_id,
                "product_id": rec["niche_product_id"],
            }
        )
    _recent_serenity_alerts = items
    return items


_recent_rec_alerts: list[dict] = []
_recent_serenity_alerts: list[dict] = []


def evaluate_global_alerts() -> list[dict]:
    """首页级全局告警（含赛道推荐）。"""
    alerts: list[dict] = []
    proposed = list_recommendations(status="proposed", limit=10)
    if proposed:
        top = proposed[0]
        alerts.append(
            {
                "level": "high",
                "type": "sector_recommendation_pending",
                "count": len(proposed),
                "message": f"有 {len(proposed)} 条赛道推荐待采纳（最新：{top['sector_name']}）",
                "action": "AdoptSectorRecommendation",
                "items": [r["sector_name"] for r in proposed[:5]],
            }
        )
    alerts.extend(_recent_rec_alerts)
    from app.services.bottleneck_recommendations import list_recommendations as list_bottleneck_recs

    pending_bn = list_bottleneck_recs(status="proposed", limit=10)
    if pending_bn:
        alerts.append(
            {
                "level": "medium",
                "type": "bottleneck_recommendation_pending",
                "count": len(pending_bn),
                "message": f"有 {len(pending_bn)} 条瓶颈确认提案待处理",
                "action": "ConfirmBottleneck",
            }
        )
    alerts.extend(_recent_bottleneck_alerts)
    from app.services.serenity_recommendations import list_recommendations as list_serenity_recs

    pending_ser = list_serenity_recs(status="proposed", limit=10)
    if pending_ser:
        alerts.append(
            {
                "level": "medium",
                "type": "serenity_recommendation_pending",
                "count": len(pending_ser),
                "message": f"有 {len(pending_ser)} 条 Serenity 路径提案待确认",
                "action": "ConfirmSerenityNiche",
            }
        )
    alerts.extend(_recent_serenity_alerts)
    return alerts


def evaluate_alerts(sector_id: str, mode: str = "fusion") -> list[dict]:
    alerts: list[dict] = []
    sector = get_sector(sector_id)

    if not is_sector_confirmed(sector_id):
        alerts.append(
            {
                "level": "high",
                "type": "sector_not_confirmed",
                "message": f"赛道「{sector['name'] if sector else sector_id}」尚未确认景气",
                "action": "ConfirmSectorBeta",
            }
        )

    pending = query_object_set(
        "PendingCandidates", filter_extra={"sector_id": sector_id, "mode": mode}
    )
    if len(pending) >= 3:
        alerts.append(
            {
                "level": "medium",
                "type": "pending_candidates",
                "count": len(pending),
                "message": f"有 {len(pending)} 个候选待人工入池确认",
                "action": "ApprovePoolEntry",
            }
        )

    bottlenecks = query_object_set("BottleneckProducts")
    hints = [p for p in bottlenecks if p.get("bottleneck_status") == "bottleneck_hint"]
    if hints:
        alerts.append(
            {
                "level": "medium",
                "type": "bottleneck_hint_unconfirmed",
                "count": len(hints),
                "message": f"{len(hints)} 个疑似瓶颈待研究员确认",
                "items": [p.get("id") or p.get("name") for p in hints[:5]],
                "action": "ConfirmBottleneck",
            }
        )

    p0 = query_object_set(
        "P0FusionCandidates", filter_extra={"sector_id": sector_id, "mode": mode}
    )
    if p0:
        alerts.append(
            {
                "level": "info",
                "type": "p0_resonance",
                "count": len(p0),
                "message": f"发现 {len(p0)} 个 P0 双逻辑共振候选",
            }
        )

    store = get_store()
    unconfirmed_niche = []
    for p in store.list_products(sector_id):
        merged = get_product(p["id"]) or p
        if merged.get("serenity_niche") and not merged.get("serenity_niche_confirmed"):
            unconfirmed_niche.append(merged)
    if unconfirmed_niche:
        alerts.append(
            {
                "level": "medium",
                "type": "serenity_niche_unconfirmed",
                "count": len(unconfirmed_niche),
                "message": f"{len(unconfirmed_niche)} 个 Serenity 小众环节待确认",
                "action": "ConfirmSerenityNiche",
            }
        )

    try:
        proposed_recs = query_object_set("ProposedSectorRecommendations")
        for rec in proposed_recs:
            rid = rec.get("sector_id")
            if rid is None or rid == sector_id:
                alerts.append(
                    {
                        "level": "high",
                        "type": "sector_recommendation",
                        "message": f"智能体推荐「{rec.get('sector_name')}」待采纳（Beta {int((rec.get('beta_score') or 0)*100)}%）",
                        "action": "AdoptSectorRecommendation",
                        "rec_id": rec.get("rec_id"),
                    }
                )
    except ValueError:
        pass

    try:
        from app.services.bottleneck_recommendations import list_recommendations as list_bn

        for rec in list_bn(sector_id=sector_id, status="proposed", limit=10):
            alerts.append(
                {
                    "level": "high" if rec.get("hint_level") == "hint_high" else "medium",
                    "type": "bottleneck_recommendation",
                    "message": f"瓶颈提案「{rec['product_name']}」待确认（提示分 {rec.get('hint_score')}）",
                    "action": "ConfirmBottleneck",
                    "rec_id": rec["rec_id"],
                    "product_id": rec["product_id"],
                }
            )
    except ValueError:
        pass

    try:
        from app.services.serenity_recommendations import list_recommendations as list_ser

        for rec in list_ser(sector_id=sector_id, status="proposed", limit=10):
            alerts.append(
                {
                    "level": "high" if rec.get("serenity_hint", 0) >= 70 else "medium",
                    "type": "serenity_recommendation",
                    "message": f"Serenity 提案「{rec['niche_product_name']}」待确认",
                    "action": "ConfirmSerenityNiche",
                    "rec_id": rec["rec_id"],
                    "product_id": rec["niche_product_id"],
                }
            )
    except ValueError:
        pass

    return alerts
