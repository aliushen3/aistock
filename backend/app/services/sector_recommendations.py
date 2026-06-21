"""赛道推荐记录存储 — PG + 内存 fallback。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import OntSectorRecommendation
from app.db.session import SessionLocal
from app.ontology import pg_store

_memory_recs: dict[str, dict] = {}


def _row_to_dict(r: OntSectorRecommendation) -> dict:
    return {
        "rec_id": r.rec_id,
        "run_id": r.run_id,
        "sector_name": r.sector_name,
        "sector_id": r.sector_id,
        "is_new": r.is_new,
        "beta_score": r.beta_score,
        "demand_growth_hint": r.demand_growth_hint,
        "signals": r.signals,
        "rationale": r.rationale,
        "terminal_products": r.terminal_products,
        "evidence_refs": r.evidence_refs,
        "risks": r.risks,
        "next_actions": r.next_actions,
        "status": r.status,
        "focus": r.focus,
        "agent_mode": r.agent_mode,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def save_recommendations(
    run_id: str,
    items: list[dict],
    focus: str | None,
    agent_mode: str,
    operator: str = "system",
) -> list[dict]:
    saved = []
    for item in items:
        rec_id = f"rec_{uuid.uuid4().hex[:12]}"
        record = {
            "rec_id": rec_id,
            "run_id": run_id,
            "sector_name": item["sector_name"],
            "sector_id": item.get("sector_id"),
            "is_new": item.get("is_new", item.get("sector_id") is None),
            "beta_score": float(item.get("beta_score", 0)),
            "demand_growth_hint": item.get("demand_growth_hint"),
            "signals": item.get("signals", {}),
            "rationale": item.get("rationale", ""),
            "terminal_products": item.get("terminal_products", []),
            "evidence_refs": item.get("evidence_refs", []),
            "risks": item.get("risks", []),
            "next_actions": item.get("next_actions", []),
            "status": "proposed",
            "focus": focus,
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
                    OntSectorRecommendation(
                        rec_id=rec_id,
                        run_id=run_id,
                        sector_name=record["sector_name"],
                        sector_id=record["sector_id"],
                        is_new=record["is_new"],
                        beta_score=record["beta_score"],
                        demand_growth_hint=record["demand_growth_hint"],
                        signals=record["signals"],
                        rationale=record["rationale"],
                        terminal_products=record["terminal_products"],
                        evidence_refs=record["evidence_refs"],
                        risks=record["risks"],
                        next_actions=record["next_actions"],
                        status="proposed",
                        focus=focus,
                        agent_mode=agent_mode,
                        operator=operator,
                    )
                )
                db.commit()
            finally:
                db.close()
    return saved


def list_recommendations(status: str | None = None, limit: int = 20) -> list[dict]:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            q = select(OntSectorRecommendation)
            if status:
                q = q.where(OntSectorRecommendation.status == status)
            rows = db.scalars(q.order_by(OntSectorRecommendation.created_at.desc()).limit(limit)).all()
            return [_row_to_dict(r) for r in rows]
        finally:
            db.close()
    items = list(_memory_recs.values())
    if status:
        items = [i for i in items if i["status"] == status]
    return sorted(items, key=lambda x: x.get("created_at") or "", reverse=True)[:limit]


def get_recommendation(rec_id: str) -> dict | None:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(OntSectorRecommendation, rec_id)
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
            row = db.get(OntSectorRecommendation, rec_id)
            if row is None:
                return _memory_recs.get(rec_id)
            row.status = status
            db.commit()
            return _row_to_dict(row)
        finally:
            db.close()
    return _memory_recs.get(rec_id)
