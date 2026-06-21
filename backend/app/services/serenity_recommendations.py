"""Serenity 逆向路径提案存储。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import OntSerenityRecommendation
from app.db.session import SessionLocal
from app.ontology import pg_store

_memory_recs: dict[str, dict] = {}


def _row_to_dict(r: OntSerenityRecommendation) -> dict:
    return {
        "rec_id": r.rec_id,
        "run_id": r.run_id,
        "sector_id": r.sector_id,
        "path_id": r.path_id,
        "niche_product_id": r.niche_product_id,
        "niche_product_name": r.niche_product_name,
        "serenity_hint": r.serenity_hint,
        "hop_count": r.hop_count,
        "node_names": r.node_names,
        "companies": r.companies,
        "rationale": r.rationale,
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
        rec_id = f"srec_{uuid.uuid4().hex[:12]}"
        record = {
            "rec_id": rec_id,
            "run_id": run_id,
            "sector_id": sector_id,
            "path_id": item["path_id"],
            "niche_product_id": item["niche_product_id"],
            "niche_product_name": item["niche_product_name"],
            "serenity_hint": float(item.get("serenity_hint", 0)),
            "hop_count": int(item.get("hop_count", 0)),
            "node_names": item.get("node_names", []),
            "companies": item.get("companies", []),
            "rationale": item.get("rationale", ""),
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
                    OntSerenityRecommendation(
                        rec_id=rec_id,
                        run_id=run_id,
                        sector_id=sector_id,
                        path_id=record["path_id"],
                        niche_product_id=record["niche_product_id"],
                        niche_product_name=record["niche_product_name"],
                        serenity_hint=record["serenity_hint"],
                        hop_count=record["hop_count"],
                        node_names=record["node_names"],
                        companies=record["companies"],
                        rationale=record["rationale"],
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
            q = select(OntSerenityRecommendation)
            if sector_id:
                q = q.where(OntSerenityRecommendation.sector_id == sector_id)
            if status:
                q = q.where(OntSerenityRecommendation.status == status)
            rows = db.scalars(q.order_by(OntSerenityRecommendation.serenity_hint.desc()).limit(limit)).all()
            return [_row_to_dict(r) for r in rows]
        finally:
            db.close()
    items = list(_memory_recs.values())
    if sector_id:
        items = [i for i in items if i["sector_id"] == sector_id]
    if status:
        items = [i for i in items if i["status"] == status]
    return sorted(items, key=lambda x: -x.get("serenity_hint", 0))[:limit]


def get_recommendation(rec_id: str) -> dict | None:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(OntSerenityRecommendation, rec_id)
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
            row = db.get(OntSerenityRecommendation, rec_id)
            if row is None:
                return _memory_recs.get(rec_id)
            row.status = status
            db.commit()
            return _row_to_dict(row)
        finally:
            db.close()
    return _memory_recs.get(rec_id)
