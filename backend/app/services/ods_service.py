"""ODS 层读写 — 产业指标、行情、公告入库与查询。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.adapters.registry import (
    get_announcement_adapter,
    get_financial_adapter,
    get_market_adapter,
    get_metrics_adapter,
    get_research_adapter,
)
from app.db.models import (
    OdsAnnouncement,
    OdsExternalReport,
    OdsFinancialStatement,
    OdsIndustryMetric,
    OdsMarketDaily,
    OdsResearchReport,
)
from app.db.session import SessionLocal
from app.ontology import pg_store
from app.services.graph_store import get_store

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
    adapter = get_metrics_adapter(adapter_name)
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
    adapter = get_market_adapter(adapter_name)
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
    adapter = get_announcement_adapter(adapter_name)
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
                existing.url = r.get("url")
                existing.source = adapter.name
            else:
                db.add(
                    OdsAnnouncement(
                        ann_id=r["ann_id"],
                        stock_code=r["stock_code"],
                        title=r["title"],
                        ann_date=r["ann_date"],
                        category=r.get("category"),
                        url=r.get("url"),
                        source=adapter.name,
                    )
                )
            upserted += 1
        db.commit()
        return {"status": "ok", "adapter": adapter.name, "count": upserted}
    finally:
        db.close()


def sync_financials(stock_codes: list[str], adapter_name: str | None = None) -> dict:
    adapter = get_financial_adapter(adapter_name)
    records = adapter.fetch_financials(stock_codes)
    if not is_ods_enabled():
        return {"status": "skipped", "count": len(records)}
    db = SessionLocal()
    try:
        upserted = 0
        for r in records:
            existing = db.scalars(
                select(OdsFinancialStatement).where(
                    OdsFinancialStatement.stock_code == r["stock_code"],
                    OdsFinancialStatement.end_date == r["end_date"],
                    OdsFinancialStatement.source == adapter.name,
                )
            ).first()
            if existing:
                existing.ann_date = r.get("ann_date")
                existing.revenue = r.get("revenue")
                existing.net_profit = r.get("net_profit")
                existing.gross_margin = r.get("gross_margin")
                existing.roe = r.get("roe")
                existing.eps = r.get("eps")
                existing.ingested_at = datetime.now(timezone.utc)
            else:
                db.add(
                    OdsFinancialStatement(
                        stock_code=r["stock_code"],
                        end_date=r["end_date"],
                        ann_date=r.get("ann_date"),
                        revenue=r.get("revenue"),
                        net_profit=r.get("net_profit"),
                        gross_margin=r.get("gross_margin"),
                        roe=r.get("roe"),
                        eps=r.get("eps"),
                        source=adapter.name,
                    )
                )
            upserted += 1
        db.commit()
        return {"status": "ok", "adapter": adapter.name, "count": upserted}
    finally:
        db.close()


def sync_external_reports(stock_codes: list[str], adapter_name: str | None = None) -> dict:
    adapter = get_research_adapter(adapter_name)
    records = adapter.fetch_research_reports(stock_codes)
    if not is_ods_enabled():
        return {"status": "skipped", "count": len(records)}
    db = SessionLocal()
    try:
        upserted = 0
        for r in records:
            existing = db.scalars(
                select(OdsExternalReport).where(
                    OdsExternalReport.report_key == r["report_key"]
                )
            ).first()
            if existing:
                existing.title = r["title"]
                existing.org_name = r.get("org_name")
                existing.rating = r.get("rating")
                existing.report_date = r.get("report_date")
                existing.url = r.get("url")
                existing.source = adapter.name
            else:
                db.add(
                    OdsExternalReport(
                        report_key=r["report_key"],
                        stock_code=r.get("stock_code"),
                        title=r["title"],
                        org_name=r.get("org_name"),
                        rating=r.get("rating"),
                        report_date=r.get("report_date"),
                        url=r.get("url"),
                        source=adapter.name,
                    )
                )
            upserted += 1
        db.commit()
        return {"status": "ok", "adapter": adapter.name, "count": upserted}
    finally:
        db.close()


_LAYER_ODS_SYNC = {
    "market": ("sync_market_daily", "tencent"),
    "research": ("sync_external_reports", "eastmoney"),
    "fundamental": ("sync_financials", "sina"),
    "announcement": ("sync_announcements", "cninfo_direct"),
}


def sync_layer_to_ods(layer: str, sector_id: str) -> dict:
    """将 ODS 就绪层通过七层直连适配器同步入库。"""
    from app.services.graph_store import sector_company_codes

    layer = (layer or "").lower()
    spec = _LAYER_ODS_SYNC.get(layer)
    if spec is None:
        raise ValueError(f"层 {layer} 不支持 ODS 同步")
    fn_name, adapter_name = spec
    store_fn = globals()[fn_name]
    store = get_store()
    codes = sector_company_codes(sector_id)
    if not codes:
        reason = "no_products" if not store.list_products(sector_id) else "no_constituents"
        message = (
            "赛道尚无产业链环节，请先在「知识抽取」确认拓扑"
            if reason == "no_products"
            else "当前赛道 0 只成分股，请先完成「同步成分股」"
        )
        return {
            "status": "skipped",
            "reason": reason,
            "message": message,
            "layer": layer,
            "sector_id": sector_id,
        }
    result = store_fn(codes, adapter_name=adapter_name)
    result["layer"] = layer
    result["sector_id"] = sector_id
    result["stock_codes"] = len(codes)
    return result


def sync_all_ods_layers(sector_id: str) -> dict:
    """按七层架构顺序同步全部 ODS 就绪层（market/research/fundamental/announcement）。"""
    if get_store().get_sector(sector_id) is None:
        raise ValueError(f"赛道不存在: {sector_id}")
    layers = list(_LAYER_ODS_SYNC.keys())
    results: dict[str, dict] = {}
    for layer in layers:
        results[layer] = sync_layer_to_ods(layer, sector_id)
    ok = sum(1 for r in results.values() if r.get("status") == "ok")
    skipped = sum(1 for r in results.values() if r.get("status") == "skipped")
    return {
        "status": "ok" if ok else ("skipped" if skipped else "partial"),
        "sector_id": sector_id,
        "layers_synced": ok,
        "layers_skipped": skipped,
        "results": results,
    }


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


def list_ods_financials(stock_code: str, limit: int = 12) -> list[dict]:
    if not is_ods_enabled():
        return []
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(OdsFinancialStatement)
            .where(OdsFinancialStatement.stock_code == stock_code)
            .order_by(OdsFinancialStatement.end_date.desc())
            .limit(limit)
        ).all()
        return [
            {
                "stock_code": r.stock_code,
                "end_date": r.end_date,
                "ann_date": r.ann_date,
                "revenue": r.revenue,
                "net_profit": r.net_profit,
                "gross_margin": r.gross_margin,
                "roe": r.roe,
                "eps": r.eps,
                "source": r.source,
            }
            for r in rows
        ]
    finally:
        db.close()


def list_ods_external_reports(stock_code: str | None = None, limit: int = 50) -> list[dict]:
    if not is_ods_enabled():
        return []
    db = SessionLocal()
    try:
        q = select(OdsExternalReport).order_by(OdsExternalReport.report_date.desc())
        if stock_code:
            q = q.where(OdsExternalReport.stock_code == stock_code)
        rows = db.scalars(q.limit(limit)).all()
        return [
            {
                "report_key": r.report_key,
                "stock_code": r.stock_code,
                "title": r.title,
                "org_name": r.org_name,
                "rating": r.rating,
                "report_date": r.report_date,
                "url": r.url,
                "source": r.source,
            }
            for r in rows
        ]
    finally:
        db.close()


def latest_market_overlay(stock_codes: list[str]) -> dict[str, dict]:
    """各代码最近一日行情，供候选池/看板回读真实数据（缺则不覆盖种子）。"""
    if not is_ods_enabled() or not stock_codes:
        return {}
    db = SessionLocal()
    try:
        out: dict[str, dict] = {}
        for code in set(stock_codes):
            row = db.scalars(
                select(OdsMarketDaily)
                .where(OdsMarketDaily.stock_code == code)
                .order_by(OdsMarketDaily.trade_date.desc())
                .limit(1)
            ).first()
            if row:
                out[code] = {
                    "close_price": row.close_price,
                    "market_cap_billion": row.market_cap_billion,
                    "pe_percentile": row.pe_percentile,
                    "trade_date": row.trade_date,
                    "source": row.source,
                }
        return out
    finally:
        db.close()


def latest_financial_overlay(stock_codes: list[str]) -> dict[str, dict]:
    """各代码最近一期财报关键科目。"""
    if not is_ods_enabled() or not stock_codes:
        return {}
    db = SessionLocal()
    try:
        out: dict[str, dict] = {}
        for code in set(stock_codes):
            row = db.scalars(
                select(OdsFinancialStatement)
                .where(OdsFinancialStatement.stock_code == code)
                .order_by(OdsFinancialStatement.end_date.desc())
                .limit(1)
            ).first()
            if row:
                out[code] = {
                    "gross_margin": row.gross_margin,
                    "roe": row.roe,
                    "revenue": row.revenue,
                    "net_profit": row.net_profit,
                    "eps": row.eps,
                    "end_date": row.end_date,
                    "source": row.source,
                }
        return out
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
            "financials": db.scalar(select(func.count()).select_from(OdsFinancialStatement)) or 0,
            "external_reports": db.scalar(select(func.count()).select_from(OdsExternalReport)) or 0,
            "adapters": __import__("app.adapters.registry", fromlist=["list_adapters"]).list_adapters(),
        }
    finally:
        db.close()
