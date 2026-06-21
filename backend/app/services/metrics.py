"""产业指标服务 — 产能/价格/扩产等动态看板数据。"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.db.models import OdsIndustryMetric, OntSectorMetric
from app.db.session import SessionLocal
from app.ontology import pg_store
from app.services.graph_store import get_store

METRICS_SEED = Path(__file__).resolve().parents[1] / "data" / "seed_metrics.json"

METRIC_LABELS = {
    "capacity_utilization": "产能利用率",
    "price_yoy": "价格同比",
    "shipment_yoy": "出货量同比",
    "gross_margin": "毛利率",
    "expansion_lead_months": "扩产周期",
    "sector_capex_yoy": "资本开支同比",
    "sector_demand_growth": "需求增速",
}


def load_metrics_seed_if_empty() -> bool:
    if not pg_store.is_db_enabled():
        return False
    from sqlalchemy import func

    db = SessionLocal()
    try:
        count = db.scalar(select(func.count()).select_from(OntSectorMetric))
        if (count or 0) > 0:
            return False
        with open(METRICS_SEED, encoding="utf-8") as f:
            seed = json.load(f)
        for m in seed.get("metrics", []):
            db.add(
                OntSectorMetric(
                    sector_id=seed["sector_id"],
                    product_id=m.get("product_id"),
                    metric_key=m["metric_key"],
                    period=m["period"],
                    value=m["value"],
                    unit=m.get("unit", ""),
                )
            )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _metrics_from_seed_file(sector_id: str) -> list[dict]:
    with open(METRICS_SEED, encoding="utf-8") as f:
        seed = json.load(f)
    if seed.get("sector_id") != sector_id:
        return []
    store = get_store()
    items = []
    for m in seed.get("metrics", []):
        pid = m.get("product_id")
        pname = store.get_product(pid)["name"] if pid and store.get_product(pid) else None
        items.append(
            {
                "sector_id": sector_id,
                "product_id": pid,
                "product_name": pname,
                "metric_key": m["metric_key"],
                "metric_label": METRIC_LABELS.get(m["metric_key"], m["metric_key"]),
                "period": m["period"],
                "value": m["value"],
                "unit": m["unit"],
            }
        )
    return items


def _metric_field(row, name: str, default=None):
    if hasattr(row, name):
        return getattr(row, name)
    if isinstance(row, dict):
        return row.get(name, default)
    return default


def _format_metric_rows(rows, sector_id: str) -> list[dict]:
    store = get_store()
    out = []
    for r in rows:
        pid = _metric_field(r, "product_id")
        mkey = _metric_field(r, "metric_key")
        out.append(
            {
                "sector_id": sector_id,
                "product_id": pid,
                "product_name": store.get_product(pid)["name"] if pid and store.get_product(pid) else None,
                "metric_key": mkey,
                "metric_label": METRIC_LABELS.get(mkey, mkey),
                "period": _metric_field(r, "period"),
                "value": _metric_field(r, "value"),
                "unit": _metric_field(r, "unit", "") or "",
                "data_source": _metric_field(r, "source", "ont") or "ont",
            }
        )
    return out


def list_sector_metrics(sector_id: str) -> list[dict]:
    """优先 ODS → ont_sector_metric → seed 文件。"""
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            ods_rows = db.scalars(
                select(OdsIndustryMetric).where(OdsIndustryMetric.sector_id == sector_id)
            ).all()
            if ods_rows:
                return _format_metric_rows(ods_rows, sector_id)
            ont_rows = db.scalars(
                select(OntSectorMetric).where(OntSectorMetric.sector_id == sector_id)
            ).all()
            if ont_rows:
                formatted = _format_metric_rows(ont_rows, sector_id)
                for x in formatted:
                    x["data_source"] = "ont_sector_metric"
                return formatted
        finally:
            db.close()
    items = _metrics_from_seed_file(sector_id)
    for x in items:
        x["data_source"] = "seed_file"
    return items


def dashboard_summary(sector_id: str) -> dict:
    metrics = list_sector_metrics(sector_id)
    store = get_store()
    sector = store.get_sector(sector_id)
    by_product: dict[str, list] = {}
    sector_level = []
    for m in metrics:
        if m["product_id"]:
            by_product.setdefault(m["product_id"], []).append(m)
        else:
            sector_level.append(m)

    product_cards = []
    for pid, ms in by_product.items():
        p = store.get_product(pid)
        if not p:
            continue
        cap = next((x for x in ms if x["metric_key"] == "capacity_utilization"), None)
        price = next((x for x in ms if x["metric_key"] in ("price_yoy", "shipment_yoy")), None)
        product_cards.append(
            {
                "product_id": pid,
                "product_name": p["name"],
                "bottleneck_status": p.get("bottleneck_status"),
                "capacity_utilization": cap["value"] if cap else None,
                "price_or_shipment_yoy": price["value"] if price else None,
                "metrics": ms,
            }
        )

    data_source = metrics[0].get("data_source", "seed") if metrics else "none"
    note = (
        f"产业指标来自 ODS（{data_source}），仅供投研跟踪参考"
        if data_source not in ("seed", "seed_import", "none", "unknown")
        else "产业指标数据，仅供投研跟踪参考"
    )
    return {
        "sector_id": sector_id,
        "sector_name": sector["name"] if sector else sector_id,
        "sector_status": sector.get("status") if sector else None,
        "sector_metrics": sector_level,
        "product_cards": sorted(product_cards, key=lambda x: -(x.get("capacity_utilization") or 0)),
        "data_source": data_source,
        "note": note,
    }


def get_sector_metrics_summary(sector_id: str) -> dict | None:
    """供赛道推荐 Agent 使用的指标信号摘要。"""
    metrics = list_sector_metrics(sector_id)
    if not metrics:
        return None
    store = get_store()
    demand = next((m["value"] for m in metrics if m["metric_key"] == "sector_demand_growth"), None)
    capex = next((m["value"] for m in metrics if m["metric_key"] == "sector_capex_yoy"), None)
    high_util, price_mom = [], []
    by_product: dict[str, list] = {}
    for m in metrics:
        if m["product_id"]:
            by_product.setdefault(m["product_id"], []).append(m)
    for pid, ms in by_product.items():
        p = store.get_product(pid)
        pname = p["name"] if p else pid
        cap = next((x for x in ms if x["metric_key"] == "capacity_utilization"), None)
        if cap and cap["value"] >= 0.9:
            high_util.append({"product_id": pid, "product_name": pname, "capacity_utilization": cap["value"]})
        price = next((x for x in ms if x["metric_key"] in ("price_yoy", "shipment_yoy")), None)
        if price and price["value"] >= 0.15:
            price_mom.append({"product_id": pid, "product_name": pname, "momentum": price["value"]})
    return {
        "sector_demand_growth": demand,
        "sector_capex_yoy": capex,
        "high_utilization_products": high_util,
        "price_momentum_products": price_mom,
    }
