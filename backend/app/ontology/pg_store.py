"""PostgreSQL Ontology 持久化读写。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import (
    OntAuditLog,
    OntCandidateEntry,
    OntKnowledgeAssertion,
    OntLinkUpstream,
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


def insert_sector(
    sector_id: str,
    name: str,
    demand_growth_hint: float | None = None,
    terminal_products: list | None = None,
    attrs: dict | None = None,
) -> bool:
    """新增赛道节点（beta_candidate），已存在则跳过。"""
    if not _db_enabled:
        return False
    db = SessionLocal()
    try:
        if db.get(OntSector, sector_id):
            return False
        db.add(
            OntSector(
                id=sector_id,
                name=name,
                status="beta_candidate",
                demand_growth_hint=demand_growth_hint,
                human_confirmed=False,
                terminal_products=terminal_products or [],
                attrs=attrs or {},
            )
        )
        db.commit()
        return True
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


def create_product(
    product_id: str,
    name: str,
    sector_id: str,
    layer: str = "material",
    attrs: dict | None = None,
) -> bool:
    """新建 OntProduct 节点（知识抽取确认 / CreateProduct Action）。"""
    if not _db_enabled:
        return False
    db = SessionLocal()
    try:
        if db.get(OntProduct, product_id):
            return False
        if db.get(OntSector, sector_id) is None:
            return False
        merged_attrs = {"created_by": "knowledge_extract", "status": "confirmed", **(attrs or {})}
        db.add(
            OntProduct(
                id=product_id,
                name=name,
                layer=layer,
                sector_id=sector_id,
                attrs=merged_attrs,
            )
        )
        db.commit()
        return True
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


def save_audit(action: str, operator: str, target: str, detail: dict | None = None) -> int | None:
    if not _db_enabled:
        return None
    db = SessionLocal()
    try:
        row = OntAuditLog(
            action=action,
            operator=operator,
            target=target,
            detail=detail or {},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def list_audits(limit: int = 100) -> list[dict]:
    if not _db_enabled:
        return []
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(OntAuditLog).order_by(OntAuditLog.id.desc()).limit(limit)
        ).all()
        return [
            {
                "id": r.id,
                "action": r.action,
                "operator": r.operator,
                "target": r.target,
                "detail": r.detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    finally:
        db.close()


def save_knowledge_assertion(
    subject_type: str,
    subject_id: str,
    predicate: str,
    object_value: str,
    operator: str,
    reason: str = "",
    evidence_refs: list | None = None,
) -> int | None:
    if not _db_enabled:
        return None
    db = SessionLocal()
    try:
        row = OntKnowledgeAssertion(
            subject_type=subject_type,
            subject_id=subject_id,
            predicate=predicate,
            object_value=object_value,
            evidence_refs=evidence_refs or [],
            reason=reason,
            operator=operator,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def add_upstream_link(source_id: str, target_id: str) -> bool:
    if not _db_enabled:
        return False
    db = SessionLocal()
    try:
        exists = db.scalar(
            select(OntLinkUpstream).where(
                OntLinkUpstream.source_id == source_id,
                OntLinkUpstream.target_id == target_id,
            )
        )
        if exists:
            return False
        db.add(OntLinkUpstream(source_id=source_id, target_id=target_id))
        db.commit()
        return True
    finally:
        db.close()


def remove_upstream_link(source_id: str, target_id: str) -> bool:
    if not _db_enabled:
        return False
    db = SessionLocal()
    try:
        row = db.scalar(
            select(OntLinkUpstream).where(
                OntLinkUpstream.source_id == source_id,
                OntLinkUpstream.target_id == target_id,
            )
        )
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()
