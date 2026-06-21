"""审计日志 — 记录所有人工确认/否决/覆盖操作。

二期落 PostgreSQL `ont_audit_log`；内存态作 fallback。
"""

from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass, field

_seq = itertools.count(1)


@dataclass
class AuditEntry:
    id: int
    action: str
    operator: str
    target: str
    detail: dict = field(default_factory=dict)


class AuditLog:
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, action: str, operator: str, target: str, detail: dict | None = None) -> AuditEntry:
        from app.ontology import pg_store

        pg_id = pg_store.save_audit(action, operator, target, detail)
        entry = AuditEntry(
            id=pg_id if pg_id is not None else next(_seq),
            action=action,
            operator=operator,
            target=target,
            detail=detail or {},
        )
        self._entries.append(entry)
        return entry

    def list_all(self, limit: int = 100) -> list[dict]:
        from app.ontology import pg_store

        if pg_store.is_db_enabled():
            items = pg_store.list_audits(limit)
            if items:
                return items
        return [asdict(e) for e in self._entries[-limit:]]


audit_log = AuditLog()
