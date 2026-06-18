"""PostgreSQL Ontology 持久化读写。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import (
    OntCandidateEntry,
    OntProduct,
    OntResearchReport,
    OntSector,
)
from app.db.session import SessionLocal

_db_enabled = False


def set_db_enabled(enabled: bool) -> None:
    global _db_enabled
    _db_enabled = enabled


def is_db_enabled() -> bool:
    return _db_enabled


def update_sector_property(sector_id: str, key: str, value) -> None:
    if not _db_enabled:
        return
    db = SessionLocal()
    try:
        row = db.get(OntSector, sector_id)
        if row is None:
            return
        if hasattr(row, key) and key not in ("attrs", "terminal_products"):
            setattr(row, key, value)
        else:
            attrs = dict(row.attrs or {})
            attrs[key] = value
            row.attrs = attrs
        db.commit()
    finally:
        db.close()


def update_product_property(product_id: str, key: str, value) -> None:
    if not _db_enabled:
        return
    db = SessionLocal()
    try:
        row = db.get(OntProduct, product_id)
        if row is None:
            return
        if hasattr(OntProduct, key) and key not in ("attrs", "provenance_ids"):
            col = getattr(OntProduct, key, None)
            if col is not None and hasattr(col, "property"):
                setattr(row, key, value)
            else:
                attrs = dict(row.attrs or {})
                attrs[key] = value
                row.attrs = attrs
        else:
            attrs = dict(row.attrs or {})
            attrs[key] = value
            row.attrs = attrs
        db.commit()
    finally:
        db.close()


def upsert_candidate_entry(
    entry_id: str,
    sector_id: str,
    mode: str,
    stock_code: str,
    status: str,
    reason: str,
    operator: str,
    priority: str | None = None,
) -> None:
    if not _db_enabled:
        return
    db = SessionLocal()
    try:
        row = db.get(OntCandidateEntry, entry_id)
        if row is None:
            row = OntCandidateEntry(
                entry_id=entry_id,
                sector_id=sector_id,
                mode=mode,
                stock_code=stock_code,
            )
            db.add(row)
        row.status = status
        row.reason = reason
        row.operator = operator
        row.priority = priority
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def get_candidate_status(entry_id: str) -> dict | None:
    if not _db_enabled:
        return None
    db = SessionLocal()
    try:
        row = db.get(OntCandidateEntry, entry_id)
        if row is None:
            return None
        return {
            "status": row.status,
            "reason": row.reason,
            "operator": row.operator,
        }
    finally:
        db.close()


def save_report(report: dict) -> None:
    if not _db_enabled:
        return
    db = SessionLocal()
    try:
        payload = {k: v for k, v in report.items() if k not in ("report_id", "status", "sector_id", "mode", "generated_by", "generated_at", "review")}
        row = OntResearchReport(
            report_id=report["report_id"],
            status=report.get("status", "draft"),
            sector_id=report["sector_id"],
            mode=report["mode"],
            generated_by=report.get("generated_by", ""),
            payload=payload,
            generated_at=datetime.fromisoformat(report["generated_at"].replace("Z", "+00:00"))
            if isinstance(report.get("generated_at"), str)
            else datetime.now(timezone.utc),
        )
        db.merge(row)
        db.commit()
    finally:
        db.close()


def get_report(report_id: str) -> dict | None:
    if not _db_enabled:
        return None
    db = SessionLocal()
    try:
        row = db.get(OntResearchReport, report_id)
        if row is None:
            return None
        return _report_row_to_dict(row)
    finally:
        db.close()


def update_report_status(report_id: str, status: str, review: dict | None = None) -> dict | None:
    if not _db_enabled:
        return None
    db = SessionLocal()
    try:
        row = db.get(OntResearchReport, report_id)
        if row is None:
            return None
        row.status = status
        if review:
            row.review = review
        db.commit()
        db.refresh(row)
        return _report_row_to_dict(row)
    finally:
        db.close()


def _report_row_to_dict(row: OntResearchReport) -> dict:
    data = {
        "report_id": row.report_id,
        "status": row.status,
        "sector_id": row.sector_id,
        "mode": row.mode,
        "generated_by": row.generated_by,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "review": row.review,
        **(row.payload or {}),
    }
    return data
