"""知识抽取 — 公告/研报文本 → 草案三元组。"""

from __future__ import annotations

import itertools
import json
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import OntKnowledgeDraft
from app.db.session import SessionLocal
from app.ontology import pg_store
from app.services.graph_store import get_store
from app.services.source_trust import enrich_relation, validate_relation_promotion

_draft_seq = itertools.count(1)
_memory_drafts: dict[str, dict] = {}


def _extract_upstream_relations(text: str, sector_id: str) -> list[dict]:
    """规则抽取：识别「A 是 B 的上游/供应」模式。"""
    store = get_store()
    products = {p["name"]: p["id"] for p in store.list_products(sector_id)}
    relations = []
    patterns = [
        r"([\u4e00-\u9fffA-Za-z0-9]+)\s*(?:是|为)\s*([\u4e00-\u9fffA-Za-z0-9]+)\s*(?:的)?上游",
        r"([\u4e00-\u9fffA-Za-z0-9]+)\s*供应\s*([\u4e00-\u9fffA-Za-z0-9]+)",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            up_name, down_name = m.group(1), m.group(2)
            up_id = products.get(up_name)
            down_id = products.get(down_name)
            if up_id and down_id:
                relations.append(
                    enrich_relation(
                        {
                            "type": "UPSTREAM_OF",
                            "source_id": up_id,
                            "source_name": up_name,
                            "target_id": down_id,
                            "target_name": down_name,
                            "confidence": "medium",
                        },
                        source_type="rule_extract",
                        source_ref="rule_pattern",
                    )
                )
    return relations


def _extract_bottleneck_hints(text: str, sector_id: str) -> list[dict]:
    store = get_store()
    hints = []
    keywords = ["瓶颈", "供不应求", "扩产周期", "扩产", "产能紧张", "产能", "认证壁垒", "涨价", "缺货"]
    if not any(k in text for k in keywords):
        return hints
    for p in store.list_products(sector_id):
        if p["name"] in text:
            hints.append(
                {
                    "type": "bottleneck_hint",
                    "product_id": p["id"],
                    "product_name": p["name"],
                    "confidence": "low",
                }
            )
    return hints


def extract_with_llm(text: str, sector_id: str, source_ref: str = "llm_v1") -> dict | None:
    """LLM 三元组抽取；无 Key 或失败时返回 None。"""
    from app.services.llm_client import chat_completion, is_llm_enabled, parse_json_response

    if not is_llm_enabled():
        return None
    store = get_store()
    products = [{"id": p["id"], "name": p["name"]} for p in store.list_products(sector_id)]
    system = (
        "你是产业知识抽取助手。从研报文本抽取产业链关系与瓶颈提示。\n"
        "输出 JSON（不要 markdown）：\n"
        '{"relations":[{"type":"UPSTREAM_OF","source_name":"","target_name":"","confidence":"high|medium|low"}],'
        '"bottleneck_hints":[{"product_name":"","confidence":"high|medium|low"}],'
        '"evidence_excerpt":""}\n'
        "source_name/target_name/product_name 优先使用给定产品列表中的名称。"
    )
    user = json.dumps({"products": products, "text": text[:8000]}, ensure_ascii=False)
    raw = chat_completion(system, user, temperature=0.2)
    if not raw:
        return None
    parsed = parse_json_response(raw)
    if not parsed:
        return None

    name_to_id = {p["name"]: p["id"] for p in products}
    relations = []
    for rel in parsed.get("relations", []):
        up_name = rel.get("source_name", "")
        down_name = rel.get("target_name", "")
        up_id = name_to_id.get(up_name)
        down_id = name_to_id.get(down_name)
        if up_id and down_id:
            relations.append(
                enrich_relation(
                    {
                        "type": "UPSTREAM_OF",
                        "source_id": up_id,
                        "source_name": up_name,
                        "target_id": down_id,
                        "target_name": down_name,
                        "confidence": rel.get("confidence", "medium"),
                    },
                    source_type="llm_extract",
                    source_ref=source_ref,
                )
            )
    hints = []
    for hint in parsed.get("bottleneck_hints", []):
        pname = hint.get("product_name", "")
        pid = name_to_id.get(pname)
        if pid:
            hints.append(
                {
                    "type": "bottleneck_hint",
                    "product_id": pid,
                    "product_name": pname,
                    "confidence": hint.get("confidence", "low"),
                }
            )
    return {
        "relations": relations,
        "bottleneck_hints": hints,
        "evidence_excerpt": parsed.get("evidence_excerpt") or text[:500],
        "extractor": "llm_v1",
    }


def extract_from_text(
    text: str,
    sector_id: str,
    prefer_llm: bool = False,
    source_type: str = "rule_extract",
    source_ref: str = "inline_text",
) -> dict:
    if prefer_llm:
        llm_result = extract_with_llm(text, sector_id, source_ref=source_ref)
        if llm_result and (llm_result.get("relations") or llm_result.get("bottleneck_hints")):
            return llm_result
    relations = _extract_upstream_relations(text, sector_id)
    for rel in relations:
        rel["source_type"] = source_type
        rel["source_ref"] = source_ref
    hints = _extract_bottleneck_hints(text, sector_id)
    return {
        "relations": relations,
        "bottleneck_hints": hints,
        "evidence_excerpt": text[:500],
        "extractor": "rule_v1",
        "source_type": source_type,
        "source_ref": source_ref,
    }


def ingest_document(
    sector_id: str,
    source_type: str,
    source_ref: str,
    content: str,
    operator: str = "analyst",
    extracted: dict | None = None,
    agent_mode: str | None = None,
) -> dict:
    payload = extracted or extract_from_text(
        content, sector_id, source_type=source_type, source_ref=source_ref
    )
    if agent_mode:
        payload = {**payload, "extractor": agent_mode}
    draft_id = f"draft_{uuid.uuid4().hex[:12]}"
    draft = {
        "draft_id": draft_id,
        "sector_id": sector_id,
        "source_type": source_type,
        "source_ref": source_ref,
        "content": content,
        "extracted": payload,
        "status": "draft",
        "operator": operator,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _memory_drafts[draft_id] = draft
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            db.add(
                OntKnowledgeDraft(
                    draft_id=draft_id,
                    sector_id=sector_id,
                    source_type=source_type,
                    source_ref=source_ref,
                    content=content,
                    extracted=payload,
                    status="draft",
                    operator=operator,
                )
            )
            db.commit()
        finally:
            db.close()
    return draft


def list_drafts(sector_id: str | None = None) -> list[dict]:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            q = select(OntKnowledgeDraft)
            if sector_id:
                q = q.where(OntKnowledgeDraft.sector_id == sector_id)
            rows = db.scalars(q.order_by(OntKnowledgeDraft.created_at.desc())).all()
            return [
                {
                    "draft_id": r.draft_id,
                    "sector_id": r.sector_id,
                    "source_type": r.source_type,
                    "source_ref": r.source_ref,
                    "extracted": r.extracted,
                    "status": r.status,
                    "operator": r.operator,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        finally:
            db.close()
    items = list(_memory_drafts.values())
    if sector_id:
        items = [d for d in items if d["sector_id"] == sector_id]
    return items


def get_draft(draft_id: str) -> dict | None:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(OntKnowledgeDraft, draft_id)
            if row is None:
                return None
            return {
                "draft_id": row.draft_id,
                "sector_id": row.sector_id,
                "source_type": row.source_type,
                "source_ref": row.source_ref,
                "content": row.content,
                "extracted": row.extracted,
                "status": row.status,
            }
        finally:
            db.close()
    return _memory_drafts.get(draft_id)


def validate_draft(draft_id: str) -> dict:
    """多源交叉 / 卖方去偏校验（F5）。"""
    draft = get_draft(draft_id)
    if draft is None:
        raise ValueError(f"草案不存在: {draft_id}")

    source_type = draft.get("source_type", "research_report")
    source_ref = draft.get("source_ref", "")
    relation_checks = []
    blocked = []
    for rel in draft["extracted"].get("relations", []):
        check = validate_relation_promotion(rel, source_type, source_ref)
        rel_result = {**rel, "validation": check}
        relation_checks.append(rel_result)
        if not check["can_confirm"]:
            blocked.append(rel_result)

    return {
        "draft_id": draft_id,
        "source_type": source_type,
        "source_ref": source_ref,
        "can_confirm_all": len(blocked) == 0,
        "blocked_count": len(blocked),
        "relations": relation_checks,
        "note": "单一研报不得单独 confirm；自反性叙事须硬源验证",
    }


def confirm_draft(draft_id: str, operator: str = "analyst", force: bool = False) -> dict:
    from app.ontology.action_executor import action_executor

    draft = get_draft(draft_id)
    if draft is None:
        raise ValueError(f"草案不存在: {draft_id}")

    validation = validate_draft(draft_id)
    if not force and not validation["can_confirm_all"]:
        raise ValueError(
            f"多源交叉验证未通过：{validation['blocked_count']} 条关系被阻断。"
            f" 请补充硬源或第二独立来源，或使用 validate 查看详情。"
        )

    applied = []
    skipped = []
    for rel in draft["extracted"].get("relations", []):
        check = validate_relation_promotion(
            rel, draft.get("source_type", "research_report"), draft.get("source_ref", "")
        )
        if not force and not check["can_confirm"]:
            skipped.append({**rel, "validation": check})
            continue
        action_executor.execute_with_params(
            action_type="CalibrateChain",
            target_type="Link.upstream_of",
            target_id=f"{rel['source_id']}:{rel['target_id']}",
            params={
                "operation": "add",
                "source_id": rel["source_id"],
                "target_id": rel["target_id"],
                "reason": f"知识抽取确认: {draft['source_ref']}",
                "evidence_refs": [],
            },
            operator=operator,
        )
        applied.append({**rel, "validation": check})
    draft["status"] = "confirmed"
    _memory_drafts[draft_id] = draft
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(OntKnowledgeDraft, draft_id)
            if row:
                row.status = "confirmed"
                db.commit()
        finally:
            db.close()
    return {
        "draft_id": draft_id,
        "status": "confirmed",
        "applied_relations": applied,
        "skipped_relations": skipped,
        "validation": validation,
    }
