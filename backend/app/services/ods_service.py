"""ODS 层读写 — 产业指标、行情、公告入库与查询。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.adapters.registry import get_adapter
from app.db.models import OdsAnnouncement, OdsIndustryMetric, OdsMarketDaily, OdsResearchReport
from app.db.session import SessionLocal
from app.ontology import pg_store

METRICS_SEED = Path(__file__).resolve().parents[1] / "data" / "seed_metrics.json"


def is_ods_enabled() -> bool:
    return pg_store.is_db_enabled()


def seed_ods_metrics_if_empty() -> bool:
    """将 seed_metrics 导入 ods_industry_metric（仅空库）。"""
    if not is_ods_enabled():
        return False
    db = SessionLocal()
    try:
        count = db.scalar(select(func.count()).select_from(OdsIndustryMetric))
        if (count or 0) > 0:
            return False
        if not METRICS_SEED.exists():
            return False
        with open(METRICS_SEED, encoding="utf-8") as f:
            seed = json.load(f)
        sector_id = seed["sector_id"]
        for m in seed.get("metrics", []):
            db.add(
                OdsIndustryMetric(
                    sector_id=sector_id,
                    product_id=m.get("product_id"),
                    metric_key=m["metric_key"],
                    period=m["period"],
                    value=m["value"],
                    unit=m.get("unit", ""),
                    source="seed_import",
                )
            )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def sync_industry_metrics(sector_id: str, adapter_name: str | None = None) -> dict:
    """从适配器拉取指标并 upsert 到 ODS。"""
    adapter = get_adapter(adapter_name)
    records = adapter.fetch_industry_metrics(sector_id)
    if not is_ods_enabled():
        return {"status": "skipped", "reason": "db_disabled", "count": len(records)}
    db = SessionLocal()
    upserted = 0
    try:
        for r in records:
            existing = db.scalars(
                select(OdsIndustryMetric).where(
                    OdsIndustryMetric.sector_id == sector_id,
                    OdsIndustryMetric.product_id == r.get("product_id"),
                    OdsIndustryMetric.metric_key == r["metric_key"],
                    OdsIndustryMetric.period == r["period"],
                    OdsIndustryMetric.source == adapter.name,
                )
            ).first()
            if existing:
                existing.value = r["value"]
                existing.unit = r.get("unit", "")
                existing.ingested_at = datetime.now(timezone.utc)
            else:
                db.add(
                    OdsIndustryMetric(
                        sector_id=sector_id,
                        product_id=r.get("product_id"),
                        metric_key=r["metric_key"],
                        period=r["period"],
                        value=r["value"],
                        unit=r.get("unit", ""),
                        source=adapter.name,
                    )
                )
            upserted += 1
        db.commit()
        return {"status": "ok", "adapter": adapter.name, "count": upserted}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def sync_market_daily(stock_codes: list[str], adapter_name: str | None = None) -> dict:
    adapter = get_adapter(adapter_name)
    records = adapter.fetch_market_daily(stock_codes)
    if not is_ods_enabled():
        return {"status": "skipped", "count": len(records)}
    db = SessionLocal()
    try:
        for r in records:
            existing = db.scalars(
                select(OdsMarketDaily).where(
                    OdsMarketDaily.stock_code == r["stock_code"],
                    OdsMarketDaily.trade_date == r["trade_date"],
                )
            ).first()
            if existing:
                existing.market_cap_billion = r.get("market_cap_billion")
                existing.pe_percentile = r.get("pe_percentile")
                existing.close_price = r.get("close_price")
            else:
                db.add(
                    OdsMarketDaily(
                        stock_code=r["stock_code"],
                        trade_date=r["trade_date"],
                        close_price=r.get("close_price"),
                        market_cap_billion=r.get("market_cap_billion"),
                        pe_percentile=r.get("pe_percentile"),
                        source=adapter.name,
                    )
                )
        db.commit()
        return {"status": "ok", "adapter": adapter.name, "count": len(records)}
    finally:
        db.close()


def sync_announcements(stock_codes: list[str], adapter_name: str | None = None) -> dict:
    adapter = get_adapter(adapter_name)
    records = adapter.fetch_announcements(stock_codes)
    if not is_ods_enabled():
        return {"status": "skipped", "count": len(records)}
    db = SessionLocal()
    try:
        upserted = 0
        for r in records:
            existing = db.get(OdsAnnouncement, r["ann_id"])
            if existing:
                existing.title = r["title"]
                existing.ann_date = r["ann_date"]
                existing.category = r.get("category")
                existing.source = adapter.name
            else:
                db.add(
                    OdsAnnouncement(
                        ann_id=r["ann_id"],
                        stock_code=r["stock_code"],
                        title=r["title"],
                        ann_date=r["ann_date"],
                        category=r.get("category"),
                        source=adapter.name,
                    )
                )
            upserted += 1
        db.commit()
        return {"status": "ok", "adapter": adapter.name, "count": upserted}
    finally:
        db.close()


def list_ods_industry_metrics(sector_id: str) -> list[dict]:
    if not is_ods_enabled():
        return []
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(OdsIndustryMetric)
            .where(OdsIndustryMetric.sector_id == sector_id)
            .order_by(OdsIndustryMetric.period.desc())
        ).all()
        return [
            {
                "sector_id": r.sector_id,
                "product_id": r.product_id,
                "metric_key": r.metric_key,
                "period": r.period,
                "value": r.value,
                "unit": r.unit,
                "source": r.source,
            }
            for r in rows
        ]
    finally:
        db.close()


def register_uploaded_report(doc: dict) -> None:
    """上传研报时同步 ODS 元数据。"""
    if not is_ods_enabled():
        return
    db = SessionLocal()
    try:
        rid = f"ods_{doc['doc_id']}"
        if db.get(OdsResearchReport, rid):
            return
        db.add(
            OdsResearchReport(
                report_id=rid,
                title=doc.get("source_ref") or doc.get("filename", ""),
                sector_id=doc.get("sector_id"),
                source="upload",
                storage_path=doc.get("storage_path"),
                char_count=doc.get("char_count", 0),
                status="indexed",
            )
        )
        db.commit()
    finally:
        db.close()


def list_ods_research_reports(sector_id: str | None = None, limit: int = 50) -> list[dict]:
    """列出 ODS 研报元数据（供动态观察清单使用）。"""
    if not is_ods_enabled():
        return []
    db = SessionLocal()
    try:
        q = select(OdsResearchReport).order_by(OdsResearchReport.ingested_at.desc())
        if sector_id:
            q = q.where(OdsResearchReport.sector_id == sector_id)
        rows = db.scalars(q.limit(limit)).all()
        return [
            {
                "report_id": r.report_id,
                "title": r.title,
                "sector_id": r.sector_id,
                "source": r.source,
                "char_count": r.char_count,
                "status": r.status,
                "ingested_at": r.ingested_at.isoformat() if r.ingested_at else None,
            }
            for r in rows
        ]
    finally:
        db.close()


def ods_stats() -> dict:
    if not is_ods_enabled():
        return {"enabled": False}
    db = SessionLocal()
    try:
        return {
            "enabled": True,
            "industry_metrics": db.scalar(select(func.count()).select_from(OdsIndustryMetric)) or 0,
            "research_reports": db.scalar(select(func.count()).select_from(OdsResearchReport)) or 0,
            "market_daily": db.scalar(select(func.count()).select_from(OdsMarketDaily)) or 0,
            "announcements": db.scalar(select(func.count()).select_from(OdsAnnouncement)) or 0,
            "adapters": __import__("app.adapters.registry", fromlist=["list_adapters"]).list_adapters(),
        }
    finally:
        db.close()
