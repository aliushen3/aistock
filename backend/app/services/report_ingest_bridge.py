"""研报 → 知识抽取桥接 — ods_external_report 标题喂入 extraction 生成草案。

em 研报适配器只入库元数据（标题/机构/评级），无正文；标题里常含「扩产/产能/
涨价」等瓶颈信号。本桥接把赛道相关研报标题聚合成文本，走既有规则/LLM 抽取链路
产出知识草案，再经 CalibrateChain/confirm 人工确认生效，形成闭环。
"""

from __future__ import annotations

import logging

from app.services.extraction import extract_from_text, ingest_document
from app.services.graph_store import get_store
from app.services.ods_service import list_ods_external_reports

logger = logging.getLogger(__name__)


def _sector_company_codes(sector_id: str) -> list[str]:
    store = get_store()
    seen: dict[str, None] = {}
    for product in store.list_products(sector_id):
        for company in store.companies_producing(product["id"]):
            seen.setdefault(company["code"], None)
    return list(seen.keys())


def _build_report_lines(codes: list[str], per_code_limit: int) -> list[str]:
    lines: list[str] = []
    for code in codes:
        for r in list_ods_external_reports(stock_code=code, limit=per_code_limit):
            title = (r.get("title") or "").strip()
            if not title:
                continue
            parts = [title]
            if r.get("org_name"):
                parts.append(f"机构:{r['org_name']}")
            if r.get("rating"):
                parts.append(f"评级:{r['rating']}")
            lines.append("；".join(parts))
    return lines


def ingest_external_reports_to_draft(
    sector_id: str,
    per_code_limit: int = 20,
    operator: str = "system",
) -> dict:
    """把赛道研报标题抽取为一份知识草案。"""
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise ValueError(f"赛道不存在: {sector_id}")

    codes = _sector_company_codes(sector_id)
    lines = _build_report_lines(codes, per_code_limit)
    text = "\n".join(lines)
    if len(text.strip()) < 20:
        return {
            "status": "empty",
            "sector_id": sector_id,
            "company_count": len(codes),
            "report_lines": len(lines),
        }

    source_ref = f"em_reports_{sector_id}"
    extracted = extract_from_text(
        text,
        sector_id,
        source_type="external_report",
        source_ref=source_ref,
    )
    draft = ingest_document(
        sector_id,
        "external_report",
        source_ref,
        text,
        operator=operator,
        extracted=extracted,
    )
    return {
        "status": "ok",
        "sector_id": sector_id,
        "company_count": len(codes),
        "report_lines": len(lines),
        "draft_id": draft["draft_id"],
        "relations": len(extracted.get("relations", [])),
        "bottleneck_hints": len(extracted.get("bottleneck_hints", [])),
        "message": "草案已生成，须经 validate / confirm 后生效",
    }
