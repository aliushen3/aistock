"""瓶颈确认提案存储 — PG + 内存 fallback。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import OntBottleneckRecommendation
from app.db.session import SessionLocal
from app.ontology import pg_store

_memory_recs: dict[str, dict] = {}


def _row_to_dict(r: OntBottleneckRecommendation) -> dict:
    return {
        "rec_id": r.rec_id,
        "run_id": r.run_id,
        "sector_id": r.sector_id,
        "product_id": r.product_id,
        "product_name": r.product_name,
        "hint_score": r.hint_score,
        "hint_level": r.hint_level,
        "hit_rules": r.hit_rules,
        "rationale": r.rationale,
        "evidence_refs": r.evidence_refs,
        "status": r.status,
        "agent_mode": r.agent_mode,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def save_recommendations(
    run_id: str,
    sector_id: str,
    items: list[dict],
    agent_mode: str,
    operator: str = "system",
) -> list[dict]:
    saved = []
    for item in items:
        rec_id = f"brec_{uuid.uuid4().hex[:12]}"
        record = {
            "rec_id": rec_id,
            "run_id": run_id,
            "sector_id": sector_id,
            "product_id": item["product_id"],
            "product_name": item["product_name"],
            "hint_score": float(item.get("hint_score", 0)),
            "hint_level": item.get("hint_level", "none"),
            "hit_rules": item.get("hit_rules", []),
            "rationale": item.get("rationale", ""),
            "evidence_refs": item.get("evidence_refs", []),
            "status": "proposed",
            "agent_mode": agent_mode,
            "operator": operator,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _memory_recs[rec_id] = record
        saved.append(record)
        if pg_store.is_db_enabled():
            db = SessionLocal()
            try:
                db.add(
                    OntBottleneckRecommendation(
                        rec_id=rec_id,
                        run_id=run_id,
                        sector_id=sector_id,
                        product_id=record["product_id"],
                        product_name=record["product_name"],
                        hint_score=record["hint_score"],
                        hint_level=record["hint_level"],
                        hit_rules=record["hit_rules"],
                        rationale=record["rationale"],
                        evidence_refs=record["evidence_refs"],
                        status="proposed",
                        agent_mode=agent_mode,
                        operator=operator,
                    )
                )
                db.commit()
            finally:
                db.close()
    return saved


def list_recommendations(
    sector_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            q = select(OntBottleneckRecommendation)
            if sector_id:
                q = q.where(OntBottleneckRecommendation.sector_id == sector_id)
            if status:
                q = q.where(OntBottleneckRecommendation.status == status)
            rows = db.scalars(q.order_by(OntBottleneckRecommendation.hint_score.desc()).limit(limit)).all()
            return [_row_to_dict(r) for r in rows]
        finally:
            db.close()
    items = list(_memory_recs.values())
    if sector_id:
        items = [i for i in items if i["sector_id"] == sector_id]
    if status:
        items = [i for i in items if i["status"] == status]
    return sorted(items, key=lambda x: -x.get("hint_score", 0))[:limit]


def get_recommendation(rec_id: str) -> dict | None:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(OntBottleneckRecommendation, rec_id)
            return _row_to_dict(row) if row else None
        finally:
            db.close()
    return _memory_recs.get(rec_id)


def update_status(rec_id: str, status: str) -> dict | None:
    if rec_id in _memory_recs:
        _memory_recs[rec_id]["status"] = status
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(OntBottleneckRecommendation, rec_id)
            if row is None:
                return _memory_recs.get(rec_id)
            row.status = status
            db.commit()
            return _row_to_dict(row)
        finally:
            db.close()
    return _memory_recs.get(rec_id)
