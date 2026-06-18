"""审计日志 — 记录所有人工确认/否决/覆盖操作。

一期内存实现；二期落 PostgreSQL（见 docs/02-knowledge-engineering.md §6 双人复核）。
所有高影响人工操作（确认赛道、入池、报告发布）都必须留痕。
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
        entry = AuditEntry(
            id=next(_seq),
            action=action,
            operator=operator,
            target=target,
            detail=detail or {},
        )
        self._entries.append(entry)
        return entry

    def list_all(self) -> list[dict]:
        return [asdict(e) for e in self._entries]


audit_log = AuditLog()
