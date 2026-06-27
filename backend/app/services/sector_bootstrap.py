"""赛道冷启动 — 采纳赛道后同步成分股并抽取研报草案。"""

from __future__ import annotations

from app.services.graph_store import get_store
from app.services.report_ingest_bridge import ingest_external_reports_to_draft


def bootstrap_sector(
    sector_id: str,
    *,
    sync_constituents: bool = True,
    ingest_reports: bool = True,
) -> dict:
    """数据驱动冷启动：成分股入图 + 研报标题 → 知识草案。"""
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise ValueError(f"赛道不存在: {sector_id}")

    out: dict = {"sector_id": sector_id, "constituents": None, "report_draft": None}

    if sync_constituents:
        try:
            from app.services.graph_ingest import sync_constituents as do_sync

            out["constituents"] = do_sync(sector_id)
        except ValueError as exc:
            out["constituents"] = {"status": "skipped", "reason": str(exc)}

    if ingest_reports:
        out["report_draft"] = ingest_external_reports_to_draft(sector_id)

    return out
