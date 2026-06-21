"""看空论点（BearCase）存储 — PG + 内存 fallback。

对齐 docs/DESIGN.md §6.4。每条 BearCase 关联候选标的，rebuttal_status 默认 unrebutted；
高 severity 且 unrebutted 时阻断入池（见 action_executor 三道闸闸三）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import OntBearCase
from app.db.session import SessionLocal
from app.ontology import pg_store

_memory_bears: dict[str, dict] = {}


def _row_to_dict(r: OntBearCase) -> dict:
    return {
        "bear_id": r.bear_id,
        "run_id": r.run_id,
        "sector_id": r.sector_id,
        "candidate_id": r.candidate_id,
        "stock_code": r.stock_code,
        "risk": r.risk,
        "dimension": r.dimension,
        "severity": r.severity,
        "probability": r.probability,
        "what_would_confirm": r.what_would_confirm,
        "citations": r.citations,
        "rebuttal": r.rebuttal,
        "rebuttal_status": r.rebuttal_status,
        "agent_mode": r.agent_mode,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def clear_bear_state() -> None:
    """测试或重置用。"""
    _memory_bears.clear()


def save_bear_cases(
    run_id: str,
    sector_id: str,
    items: list[dict],
    agent_mode: str = "rule_v1",
    operator: str = "system",
) -> list[dict]:
    saved = []
    for item in items:
        bear_id = f"bear_{uuid.uuid4().hex[:12]}"
        record = {
            "bear_id": bear_id,
            "run_id": run_id,
            "sector_id": sector_id,
            "candidate_id": item.get("candidate_id"),
            "stock_code": item["stock_code"],
            "risk": item.get("risk", ""),
            "dimension": item.get("dimension", ""),
            "severity": item.get("severity", "medium"),
            "probability": item.get("probability", "medium"),
            "what_would_confirm": item.get("what_would_confirm", ""),
            "citations": item.get("citations", []),
            "rebuttal": None,
            "rebuttal_status": "unrebutted",
            "agent_mode": agent_mode,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _memory_bears[bear_id] = record
        saved.append(record)
        if pg_store.is_db_enabled():
            db = SessionLocal()
            try:
                db.add(
                    OntBearCase(
                        bear_id=bear_id,
                        run_id=run_id,
                        sector_id=sector_id,
                        candidate_id=record["candidate_id"],
                        stock_code=record["stock_code"],
                        risk=record["risk"],
                        dimension=record["dimension"],
                        severity=record["severity"],
                        probability=record["probability"],
                        what_would_confirm=record["what_would_confirm"],
                        citations=record["citations"],
                        rebuttal_status="unrebutted",
                        operator=operator,
                        agent_mode=agent_mode,
                    )
                )
                db.commit()
            finally:
                db.close()
    return saved


def list_bear_cases(
    sector_id: str | None = None,
    stock_code: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 100,
) -> list[dict]:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            q = select(OntBearCase)
            if sector_id:
                q = q.where(OntBearCase.sector_id == sector_id)
            if stock_code:
                q = q.where(OntBearCase.stock_code == stock_code)
            if status:
                q = q.where(OntBearCase.rebuttal_status == status)
            if severity:
                q = q.where(OntBearCase.severity == severity)
            rows = db.scalars(q.order_by(OntBearCase.created_at.desc()).limit(limit)).all()
            return [_row_to_dict(r) for r in rows]
        finally:
            db.close()
    items = list(_memory_bears.values())
    if sector_id:
        items = [i for i in items if i["sector_id"] == sector_id]
    if stock_code:
        items = [i for i in items if i["stock_code"] == stock_code]
    if status:
        items = [i for i in items if i["rebuttal_status"] == status]
    if severity:
        items = [i for i in items if i["severity"] == severity]
    return items[:limit]


def get_bear_case(bear_id: str) -> dict | None:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(OntBearCase, bear_id)
            return _row_to_dict(row) if row else None
        finally:
            db.close()
    return _memory_bears.get(bear_id)


def set_rebuttal(bear_id: str, rebuttal: str, operator: str = "analyst") -> dict | None:
    if bear_id in _memory_bears:
        _memory_bears[bear_id]["rebuttal"] = rebuttal
        _memory_bears[bear_id]["rebuttal_status"] = "rebutted"
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(OntBearCase, bear_id)
            if row is None:
                return _memory_bears.get(bear_id)
            row.rebuttal = rebuttal
            row.rebuttal_status = "rebutted"
            row.operator = operator
            db.commit()
            return _row_to_dict(row)
        finally:
            db.close()
    return _memory_bears.get(bear_id)


def candidate_bear_status(stock_code: str, sector_id: str | None = None) -> str:
    """候选标的的空头闸状态：unrebutted_high | rebutted | none。

    用于三道闸闸三与候选池展示。
    """
    bears = list_bear_cases(sector_id=sector_id, stock_code=stock_code)
    if not bears:
        return "none"
    if any(b["severity"] == "high" and b["rebuttal_status"] == "unrebutted" for b in bears):
        return "unrebutted_high"
    if all(b["rebuttal_status"] == "rebutted" for b in bears):
        return "rebutted"
    return "none"
