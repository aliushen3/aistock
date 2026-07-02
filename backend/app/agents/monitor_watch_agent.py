"""动态监控智能体 — Object Set 扫描 + 提案超时 + 指标异动。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.services.watchlist_service import list_watchlist_sector_ids
from app.services.bottleneck_recommendations import list_recommendations as list_bottleneck
from app.services.graph_store import get_store
from app.services.metrics import get_sector_metrics_summary
from app.services.object_set_alerts import evaluate_alerts, evaluate_global_alerts
from app.services.ods_service import ods_stats
from app.services.sector_recommendations import list_recommendations as list_sector_recs
from app.services.serenity_recommendations import list_recommendations as list_serenity
from app.services.workflow import is_sector_confirmed


def _scan_proposal_backlog(sector_id: str) -> list[dict]:
    alerts = []
    sector_recs = list_sector_recs(status="proposed", limit=20)
    bn_recs = list_bottleneck(sector_id=sector_id, status="proposed", limit=20)
    ser_recs = list_serenity(sector_id=sector_id, status="proposed", limit=20)

    if sector_recs:
        alerts.append(
            {
                "type": "backlog_sector_recommendations",
                "level": "high",
                "count": len(sector_recs),
                "message": f"{len(sector_recs)} 条赛道推荐待采纳",
                "action": "AdoptSectorRecommendation",
            }
        )
    if bn_recs:
        alerts.append(
            {
                "type": "backlog_bottleneck_recommendations",
                "level": "medium",
                "count": len(bn_recs),
                "message": f"{len(bn_recs)} 条瓶颈提案待 ConfirmBottleneck",
                "action": "ConfirmBottleneck",
            }
        )
    if ser_recs:
        alerts.append(
            {
                "type": "backlog_serenity_recommendations",
                "level": "medium",
                "count": len(ser_recs),
                "message": f"{len(ser_recs)} 条 Serenity 路径待 ConfirmSerenityNiche",
                "action": "ConfirmSerenityNiche",
            }
        )
    return alerts


def _scan_metric_anomalies(sector_id: str) -> list[dict]:
    alerts = []
    summary = get_sector_metrics_summary(sector_id)
    if not summary:
        return alerts
    if summary.get("sector_demand_growth") is not None and summary["sector_demand_growth"] < 0.1:
        alerts.append(
            {
                "type": "metric_demand_slowdown",
                "level": "medium",
                "message": f"赛道需求增速偏低（{summary['sector_demand_growth']}）",
                "action": "ReviewSectorBeta",
            }
        )
    high_util = summary.get("high_utilization_products") or []
    if len(high_util) >= 2:
        alerts.append(
            {
                "type": "metric_high_utilization",
                "level": "info",
                "count": len(high_util),
                "message": f"{len(high_util)} 个产品产能利用率 ≥90%，建议复核瓶颈",
                "action": "ConfirmBottleneck",
            }
        )
    return alerts


def _scan_freshness_lifecycle(sector_id: str) -> list[dict]:
    """保鲜过期 + 瓶颈生命周期扫描（主线二）。"""
    from app.ontology.property_overlays import merge_product
    from app.services.freshness import product_freshness

    alerts = []
    store = get_store()
    stale, easing = [], []
    for p in store.list_products(sector_id):
        merged = merge_product(p, p["id"]) or p
        if product_freshness(merged)["freshness"] == "stale":
            stale.append(p["name"])
        if merged.get("bottleneck_status") in ("bottleneck_easing", "bottleneck_expired"):
            easing.append(p["name"])
    if stale:
        alerts.append(
            {
                "type": "knowledge_stale",
                "level": "medium",
                "count": len(stale),
                "message": f"{len(stale)} 个环节知识已过期（stale），需复核刷新：{stale[:3]}",
                "action": "CalibrateChain",
            }
        )
    if easing:
        alerts.append(
            {
                "type": "bottleneck_easing",
                "level": "high",
                "count": len(easing),
                "message": f"{len(easing)} 个瓶颈进入缓解/失效，相关候选需复核：{easing[:3]}",
                "action": "ConfirmBottleneckEasing",
            }
        )
    return alerts


def _scan_bear_falsifiers(sector_id: str, mode: str = "fusion") -> list[dict]:
    """证伪条件跟踪（主线一延伸）：已入池标的的空头论点 what_would_confirm 持续盯防。

    空头论点被 rebut 不代表风险消失——其证伪条件（what_would_confirm）注册为监控项，
    研究员在组合跟踪页可对照最新公告/指标判断是否应验；应验则触发候选复核。
    """
    from app.services.bearcase_store import list_bear_cases
    from app.services.candidate_pool import build_pool

    store = get_store()
    try:
        confirmed_codes = {
            it["stock_code"]
            for it in build_pool(store, sector_id, mode)
            if it.get("status") == "confirmed"
        }
    except Exception:
        return []
    if not confirmed_codes:
        return []

    watch_items = []
    for bear in list_bear_cases(sector_id=sector_id, limit=200):
        if bear["stock_code"] not in confirmed_codes:
            continue
        if bear.get("severity") not in ("high", "medium"):
            continue
        condition = (bear.get("what_would_confirm") or "").strip()
        if not condition:
            continue
        watch_items.append(
            {
                "stock_code": bear["stock_code"],
                "risk": bear.get("risk"),
                "severity": bear.get("severity"),
                "rebuttal_status": bear.get("rebuttal_status"),
                "what_would_confirm": condition,
            }
        )
    if not watch_items:
        return []
    return [
        {
            "type": "bear_falsifier_watch",
            "level": "medium",
            "count": len(watch_items),
            "message": (
                f"{len(watch_items)} 条已入池标的的空头证伪条件在盯防中，"
                f"如出现对应事件（如 {watch_items[0]['what_would_confirm'][:30]}…）请复核持仓逻辑"
            ),
            "action": "ReviewPoolEntry",
            "items": watch_items[:10],
        }
    ]


def run_monitor_watch_agent(
    sector_id: str | None = None,
    mode: str = "fusion",
    operator: str = "analyst",
) -> dict:
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    store = get_store()
    if sector_id:
        sectors = [sector_id]
    else:
        sectors = list_watchlist_sector_ids()
    if not sectors:
        sectors = [s["id"] for s in store.list_sectors()]

    all_alerts: list[dict] = []
    sector_summaries: list[dict] = []

    for sid in sectors:
        if store.get_sector(sid) is None:
            continue
        sector_alerts = evaluate_alerts(sid, mode=mode)
        sector_alerts.extend(_scan_proposal_backlog(sid))
        sector_alerts.extend(_scan_metric_anomalies(sid))
        sector_alerts.extend(_scan_freshness_lifecycle(sid))
        sector_alerts.extend(_scan_bear_falsifiers(sid, mode=mode))
        if not is_sector_confirmed(sid):
            sector_alerts.insert(
                0,
                {
                    "type": "sector_gate_open",
                    "level": "high",
                    "message": f"赛道 {sid} 未确认景气，门控步骤不可用",
                    "action": "ConfirmSectorBeta",
                },
            )
        sector_summaries.append(
            {
                "sector_id": sid,
                "confirmed": is_sector_confirmed(sid),
                "alert_count": len(sector_alerts),
            }
        )
        for a in sector_alerts:
            item = dict(a)
            item["sector_id"] = sid
            all_alerts.append(item)

    global_alerts = evaluate_global_alerts()
    ods = ods_stats()

    return {
        "run_id": run_id,
        "agent": "monitor_watch_v1",
        "agent_mode": "scan_v1",
        "operator": operator,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "sectors_scanned": len(sector_summaries),
        "sector_summaries": sector_summaries,
        "alert_count": len(all_alerts) + len(global_alerts),
        "alerts": all_alerts,
        "global_alerts": global_alerts,
        "ods": ods,
        "disclaimer": "监控告警需人工路由至对应 Ontology Action",
    }
