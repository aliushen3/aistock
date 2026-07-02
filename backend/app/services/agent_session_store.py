"""Agent 会话持久化 — Redis 缓存 + DB + 内存 fallback。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import AGENT_SESSION_REDIS_TTL
from app.db.models import AgentSessionRecord
from app.db.session import SessionLocal
from app.ontology import pg_store
from app.services.redis_client import is_redis_available

_memory_sessions: dict[str, dict[str, Any]] = {}
_CACHE_PREFIX = "aistock:agent_session:"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:12]}"


def _cache_key(session_id: str) -> str:
    return f"{_CACHE_PREFIX}{session_id}"


def _row_to_dict(row: AgentSessionRecord) -> dict[str, Any]:
    return {
        "session_id": row.session_id,
        "operator": row.operator,
        "sector_id": row.sector_id,
        "focus": row.focus,
        "workflow_step": row.workflow_step,
        "messages": row.messages or [],
        "ui_blocks": row.ui_blocks or [],
        "chips": row.chips or [],
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _cache_get(session_id: str) -> dict[str, Any] | None:
    if not is_redis_available():
        return None
    try:
        from app.services.redis_client import get_redis_client

        raw = get_redis_client().get(_cache_key(session_id))
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return None


def _cache_set(session_id: str, payload: dict[str, Any]) -> None:
    if not is_redis_available():
        return
    try:
        from app.services.redis_client import get_redis_client

        get_redis_client().setex(_cache_key(session_id), AGENT_SESSION_REDIS_TTL, json.dumps(payload, default=str))
    except Exception:
        pass


def _cache_delete(session_id: str) -> None:
    if not is_redis_available():
        return
    try:
        from app.services.redis_client import get_redis_client

        get_redis_client().delete(_cache_key(session_id))
    except Exception:
        pass


def create_session(
    *,
    operator: str = "analyst",
    sector_id: str | None = None,
    focus: str | None = None,
    workflow_step: int | None = None,
    messages: list[dict] | None = None,
    ui_blocks: list[dict] | None = None,
    chips: list[str] | None = None,
) -> dict[str, Any]:
    session_id = _new_session_id()
    payload = {
        "session_id": session_id,
        "operator": operator,
        "sector_id": sector_id,
        "focus": focus,
        "workflow_step": workflow_step,
        "messages": messages or [],
        "ui_blocks": ui_blocks or [],
        "chips": chips or [],
        "created_at": _now().isoformat(),
        "updated_at": _now().isoformat(),
    }
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = AgentSessionRecord(
                session_id=session_id,
                operator=operator,
                sector_id=sector_id,
                focus=focus,
                workflow_step=workflow_step,
                messages=payload["messages"],
                ui_blocks=payload["ui_blocks"],
                chips=payload["chips"],
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            payload = _row_to_dict(row)
        finally:
            db.close()
    else:
        _memory_sessions[session_id] = payload
    _cache_set(session_id, payload)
    return payload


def get_session(session_id: str) -> dict[str, Any] | None:
    cached = _cache_get(session_id)
    if cached:
        return cached

    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(AgentSessionRecord, session_id)
            if row is None:
                return None
            payload = _row_to_dict(row)
            _cache_set(session_id, payload)
            return payload
        finally:
            db.close()

    payload = _memory_sessions.get(session_id)
    if payload:
        _cache_set(session_id, payload)
    return payload


def update_session(session_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {"sector_id", "focus", "workflow_step", "messages", "ui_blocks", "chips", "operator"}
    data = {k: v for k, v in patch.items() if k in allowed}
    if not data:
        return get_session(session_id)

    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(AgentSessionRecord, session_id)
            if row is None:
                return None
            for k, v in data.items():
                setattr(row, k, v)
            row.updated_at = _now()
            db.commit()
            db.refresh(row)
            payload = _row_to_dict(row)
            _cache_set(session_id, payload)
            return payload
        finally:
            db.close()

    existing = _memory_sessions.get(session_id)
    if existing is None:
        return None
    existing.update(data)
    existing["updated_at"] = _now().isoformat()
    _cache_set(session_id, existing)
    return existing


def delete_session(session_id: str) -> bool:
    _cache_delete(session_id)
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(AgentSessionRecord, session_id)
            if row is None:
                return False
            db.delete(row)
            db.commit()
            return True
        finally:
            db.close()
    return _memory_sessions.pop(session_id, None) is not None
