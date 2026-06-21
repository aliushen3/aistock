"""上传研报元数据存储（PG + 内存 fallback）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import OntUploadedDocument
from app.db.session import SessionLocal
from app.ontology import pg_store

_memory_docs: dict[str, dict] = {}


def create_document_record(
    sector_id: str,
    source_ref: str,
    filename: str,
    content_type: str,
    storage_path: str | None,
    char_count: int,
    chunk_count: int,
    operator: str = "analyst",
) -> dict:
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    record = {
        "doc_id": doc_id,
        "sector_id": sector_id,
        "source_ref": source_ref,
        "filename": filename,
        "content_type": content_type,
        "storage_path": storage_path,
        "char_count": char_count,
        "chunk_count": chunk_count,
        "status": "indexed",
        "operator": operator,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _memory_docs[doc_id] = record
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            db.add(
                OntUploadedDocument(
                    doc_id=doc_id,
                    sector_id=sector_id,
                    source_ref=source_ref,
                    filename=filename,
                    content_type=content_type,
                    storage_path=storage_path,
                    char_count=char_count,
                    chunk_count=chunk_count,
                    status="indexed",
                    operator=operator,
                )
            )
            db.commit()
        finally:
            db.close()
    return record


def list_documents(sector_id: str | None = None) -> list[dict]:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            q = select(OntUploadedDocument)
            if sector_id:
                q = q.where(OntUploadedDocument.sector_id == sector_id)
            rows = db.scalars(q.order_by(OntUploadedDocument.created_at.desc())).all()
            return [
                {
                    "doc_id": r.doc_id,
                    "sector_id": r.sector_id,
                    "source_ref": r.source_ref,
                    "filename": r.filename,
                    "content_type": r.content_type,
                    "storage_path": r.storage_path,
                    "char_count": r.char_count,
                    "chunk_count": r.chunk_count,
                    "status": r.status,
                    "operator": r.operator,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        finally:
            db.close()
    items = list(_memory_docs.values())
    if sector_id:
        items = [d for d in items if d["sector_id"] == sector_id]
    return sorted(items, key=lambda x: x.get("created_at") or "", reverse=True)


def get_document(doc_id: str) -> dict | None:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(OntUploadedDocument, doc_id)
            if row is None:
                return None
            return {
                "doc_id": row.doc_id,
                "sector_id": row.sector_id,
                "source_ref": row.source_ref,
                "filename": row.filename,
                "content_type": row.content_type,
                "storage_path": row.storage_path,
                "char_count": row.char_count,
                "chunk_count": row.chunk_count,
                "status": row.status,
                "operator": row.operator,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        finally:
            db.close()
    return _memory_docs.get(doc_id)
