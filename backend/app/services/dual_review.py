"""双人复核工作流。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import OntPendingReview
from app.db.session import SessionLocal
from app.ontology import pg_store

_memory_pending: dict[str, dict] = {}


def create_pending(
    action_type: str,
    target_type: str,
    target_id: str,
    params: dict,
    operator: str,
) -> dict:
    pending_id = f"pr_{uuid.uuid4().hex[:12]}"
    row = {
        "pending_id": pending_id,
        "action_type": action_type,
        "target_type": target_type,
        "target_id": target_id,
        "params": params,
        "first_operator": operator,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _memory_pending[pending_id] = row
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            db.add(
                OntPendingReview(
                    pending_id=pending_id,
                    action_type=action_type,
                    target_type=target_type,
                    target_id=target_id,
                    params=params,
                    first_operator=operator,
                    status="pending",
                )
            )
            db.commit()
        finally:
            db.close()
    return row


def find_pending(action_type: str, target_type: str, target_id: str) -> dict | None:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.scalar(
                select(OntPendingReview).where(
                    OntPendingReview.action_type == action_type,
                    OntPendingReview.target_type == target_type,
                    OntPendingReview.target_id == target_id,
                    OntPendingReview.status == "pending",
                )
            )
            if row:
                return {
                    "pending_id": row.pending_id,
                    "action_type": row.action_type,
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "params": row.params,
                    "first_operator": row.first_operator,
                    "status": row.status,
                }
        finally:
            db.close()
    for p in _memory_pending.values():
        if (
            p["action_type"] == action_type
            and p["target_type"] == target_type
            and p["target_id"] == target_id
            and p["status"] == "pending"
        ):
            return p
    return None


def approve_pending(pending_id: str, second_operator: str) -> dict | None:
    pending = _memory_pending.get(pending_id)
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(OntPendingReview, pending_id)
            if row:
                pending = {
                    "pending_id": row.pending_id,
                    "action_type": row.action_type,
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "params": row.params,
                    "first_operator": row.first_operator,
                    "status": row.status,
                }
        finally:
            db.close()
    if pending is None or pending["status"] != "pending":
        return None
    if pending["first_operator"] == second_operator:
        raise ValueError("双人复核须由不同操作者执行")
    pending["status"] = "approved"
    pending["second_operator"] = second_operator
    _memory_pending[pending_id] = pending
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(OntPendingReview, pending_id)
            if row:
                row.status = "approved"
                db.commit()
        finally:
            db.close()
    return pending


def list_pending(limit: int = 50) -> list[dict]:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            rows = db.scalars(
                select(OntPendingReview)
                .where(OntPendingReview.status == "pending")
                .order_by(OntPendingReview.created_at.desc())
                .limit(limit)
            ).all()
            return [
                {
                    "pending_id": r.pending_id,
                    "action_type": r.action_type,
                    "target_type": r.target_type,
                    "target_id": r.target_id,
                    "first_operator": r.first_operator,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        finally:
            db.close()
    return [p for p in _memory_pending.values() if p["status"] == "pending"][:limit]
