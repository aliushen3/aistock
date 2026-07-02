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

_VALID_LAYERS = {"terminal", "mid", "material", "consumable"}


def slug_product_id(name: str, sector_id: str) -> str:
    ascii_part = re.sub(r"[^a-zA-Z0-9]", "", name.lower())[:20]
    prefix = sector_id.replace("sector_", "")[:10]
    if ascii_part:
        return f"prod_{prefix}_{ascii_part}"[:64]
    return f"prod_{uuid.uuid4().hex[:8]}"


def _clean_product_name(name: str) -> str:
    name = (name or "").strip()
    if name.endswith("的"):
        return name[:-1]
    return name


def _register_new_product(
    name_to_id: dict[str, str],
    new_products: list[dict],
    name: str,
    sector_id: str,
    layer: str = "material",
    confidence: str = "medium",
) -> str | None:
    name = _clean_product_name(name)
    if not name:
        return None
    if name in name_to_id:
        return name_to_id[name]
    for item in new_products:
        if item["name"] == name:
            return item["product_id"]
    store = get_store()
    pid = slug_product_id(name, sector_id)
    while store.get_product(pid) or any(item["product_id"] == pid for item in new_products):
        pid = slug_product_id(f"{name}_{uuid.uuid4().hex[:4]}", sector_id)
    entry = {
        "product_id": pid,
        "name": name,
        "layer": layer if layer in _VALID_LAYERS else "material",
        "sector_id": sector_id,
        "is_new": True,
        "confidence": confidence,
    }
    new_products.append(entry)
    name_to_id[name] = pid
    return pid


def normalize_extraction(
    raw: dict,
    sector_id: str,
    source_type: str = "rule_extract",
    source_ref: str = "",
) -> dict:
    """对齐已有产品，并为未知名称生成 new_products 草案节点。"""
    store = get_store()
    name_to_id = {p["name"]: p["id"] for p in store.list_products(sector_id)}
    new_products: list[dict] = []

    for item in raw.get("new_products") or []:
        name = _clean_product_name(item.get("name") or item.get("product_name") or "")
        if not name:
            continue
        layer = item.get("layer") or "material"
        confidence = item.get("confidence", "medium")
        pid = item.get("product_id")
        if pid and not store.get_product(pid):
            new_products.append(
                {
                    "product_id": pid,
                    "name": name,
                    "layer": layer if layer in _VALID_LAYERS else "material",
                    "sector_id": sector_id,
                    "is_new": True,
                    "confidence": confidence,
                }
            )
            name_to_id[name] = pid
        else:
            _register_new_product(name_to_id, new_products, name, sector_id, layer, confidence)

    relations: list[dict] = []
    for rel in raw.get("relations") or []:
        up_name = _clean_product_name(rel.get("source_name") or "")
        down_name = _clean_product_name(rel.get("target_name") or "")
        up_id = rel.get("source_id") or name_to_id.get(up_name)
        down_id = rel.get("target_id") or name_to_id.get(down_name)
        if not up_id and up_name:
            up_id = _register_new_product(name_to_id, new_products, up_name, sector_id)
        if not down_id and down_name:
            down_id = _register_new_product(name_to_id, new_products, down_name, sector_id)
        if not up_id or not down_id:
            continue
        st = rel.get("source_type") or source_type
        sr = rel.get("source_ref") or source_ref
        relations.append(
            enrich_relation(
                {
                    "type": "UPSTREAM_OF",
                    "source_id": up_id,
                    "source_name": up_name or (store.get_product(up_id) or {}).get("name", up_id),
                    "target_id": down_id,
                    "target_name": down_name or (store.get_product(down_id) or {}).get("name", down_id),
                    "confidence": rel.get("confidence", "medium"),
                },
                source_type=st,
                source_ref=sr,
            )
        )

    hints: list[dict] = []
    for hint in raw.get("bottleneck_hints") or []:
        pname = _clean_product_name(hint.get("product_name") or "")
        pid = hint.get("product_id") or name_to_id.get(pname)
        if not pid and pname:
            pid = _register_new_product(
                name_to_id,
                new_products,
                pname,
                sector_id,
                confidence=hint.get("confidence", "low"),
            )
        if not pid:
            continue
        product = store.get_product(pid) or next((np for np in new_products if np["product_id"] == pid), None)
        hints.append(
            {
                "type": "bottleneck_hint",
                "product_id": pid,
                "product_name": pname or (product.get("name") if product else pid),
                "confidence": hint.get("confidence", "low"),
            }
        )

    return {
        "relations": relations,
        "bottleneck_hints": hints,
        "new_products": new_products,
        "evidence_excerpt": raw.get("evidence_excerpt", ""),
        "extractor": raw.get("extractor", "rule_v1"),
        "source_type": source_type,
        "source_ref": source_ref,
    }


def _extract_upstream_relations(text: str, sector_id: str) -> list[dict]:
    """规则抽取：识别「A 是 B 的上游/供应」模式。"""
    store = get_store()
    products = {p["name"]: p["id"] for p in store.list_products(sector_id)}
    relations = []
    patterns = [
        r"([\u4e00-\u9fffA-Za-z0-9]+)\s*(?:是|为)\s*([\u4e00-\u9fffA-Za-z0-9]+?)\s*(?:的\s*)?上游",
        r"([\u4e00-\u9fffA-Za-z0-9]+)\s*供应\s*([\u4e00-\u9fffA-Za-z0-9]+)",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            up_name, down_name = m.group(1), m.group(2)
            up_id = products.get(up_name)
            down_id = products.get(down_name)
            relations.append(
                {
                    "type": "UPSTREAM_OF",
                    "source_id": up_id,
                    "source_name": up_name,
                    "target_id": down_id,
                    "target_name": down_name,
                    "confidence": "medium",
                }
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
        "你是产业知识抽取助手。从研报文本抽取产业链关系、潜在新产品节点与瓶颈提示。\n"
        "输出 JSON（不要 markdown）：\n"
        '{"new_products":[{"name":"","layer":"material|mid|terminal|consumable","confidence":"high|medium|low"}],'
        '"relations":[{"type":"UPSTREAM_OF","source_name":"","target_name":"","confidence":"high|medium|low"}],'
        '"bottleneck_hints":[{"product_name":"","confidence":"high|medium|low"}],'
        '"evidence_excerpt":""}\n'
        "已知产品优先复用；产业链中出现但不在列表的新环节写入 new_products。"
    )
    user = json.dumps({"products": products, "text": text[:8000]}, ensure_ascii=False)
    raw = chat_completion(system, user, temperature=0.2)
    if not raw:
        return None
    parsed = parse_json_response(raw)
    if not parsed:
        return None

    payload = {
        "new_products": parsed.get("new_products", []),
        "relations": parsed.get("relations", []),
        "bottleneck_hints": parsed.get("bottleneck_hints", []),
        "evidence_excerpt": parsed.get("evidence_excerpt") or text[:500],
        "extractor": "llm_v1",
    }
    return normalize_extraction(payload, sector_id, "llm_extract", source_ref)


def extract_from_text(
    text: str,
    sector_id: str,
    prefer_llm: bool = False,
    source_type: str = "rule_extract",
    source_ref: str = "inline_text",
) -> dict:
    if prefer_llm:
        llm_result = extract_with_llm(text, sector_id, source_ref=source_ref)
        if llm_result and (
            llm_result.get("relations")
            or llm_result.get("bottleneck_hints")
            or llm_result.get("new_products")
        ):
            return llm_result
    relations = _extract_upstream_relations(text, sector_id)
    hints = _extract_bottleneck_hints(text, sector_id)
    raw = {
        "relations": relations,
        "bottleneck_hints": hints,
        "evidence_excerpt": text[:500],
        "extractor": "rule_v1",
    }
    return normalize_extraction(raw, sector_id, source_type, source_ref)


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
    if extracted and "new_products" not in payload:
        payload = normalize_extraction(payload, sector_id, source_type, source_ref)
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

    new_products = draft["extracted"].get("new_products", [])
    product_checks = []
    for np in new_products:
        store = get_store()
        exists = store.get_product(np.get("product_id", "")) is not None
        product_checks.append({**np, "already_exists": exists})

    return {
        "draft_id": draft_id,
        "source_type": source_type,
        "source_ref": source_ref,
        "can_confirm_all": len(blocked) == 0,
        "blocked_count": len(blocked),
        "relations": relation_checks,
        "new_products": product_checks,
        "new_product_count": len(new_products),
        "note": "单一研报不得单独 confirm 关系；新产品节点可在 force 确认时入库",
    }


def confirm_draft(draft_id: str, operator: str = "analyst", force: bool = False) -> dict:
    from app.ontology import object_store
    from app.ontology.action_executor import ActionError, action_executor

    draft = get_draft(draft_id)
    if draft is None:
        raise ValueError(f"草案不存在: {draft_id}")

    validation = validate_draft(draft_id)
    if not force and not validation["can_confirm_all"]:
        raise ValueError(
            f"多源交叉验证未通过：{validation['blocked_count']} 条关系被阻断。"
            f" 请补充硬源或第二独立来源，或使用 validate 查看详情。"
        )

    applied_products = []
    for np in draft["extracted"].get("new_products", []):
        try:
            action_executor.execute_with_params(
                action_type="CreateProduct",
                target_type="Sector",
                target_id=draft["sector_id"],
                params={
                    "product_id": np["product_id"],
                    "name": np["name"],
                    "layer": np.get("layer", "material"),
                    "reason": f"知识抽取确认: {draft['source_ref']}",
                    "source_ref": draft["source_ref"],
                },
                operator=operator,
            )
            applied_products.append(np)
        except ActionError as exc:
            if exc.code != "already_exists":
                raise

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

    applied_hints = []
    for hint in draft["extracted"].get("bottleneck_hints", []):
        pid = hint.get("product_id")
        if not pid:
            continue
        object_store.set_object_property("Product", pid, "bottleneck_status", "bottleneck_hint")
        applied_hints.append(hint)

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
    bootstrap_result = None
    from app.services.graph_store import get_store, invalidate_store_cache, sector_company_codes

    invalidate_store_cache()
    sid = draft["sector_id"]
    store = get_store()
    stats_after = {
        "products": len(store.list_products(sid)),
        "companies": len(sector_company_codes(sid)),
    }
    if stats_after["products"] == 0 or stats_after["companies"] == 0:
        from app.services.sector_bootstrap import bootstrap_sector

        bootstrap_result = bootstrap_sector(
            sid, sync_constituents=True, ingest_reports=False
        )
        invalidate_store_cache()
        store = get_store()
        stats_after = {
            "products": len(store.list_products(sid)),
            "companies": len(sector_company_codes(sid)),
        }

    return {
        "draft_id": draft_id,
        "status": "confirmed",
        "applied_products": applied_products,
        "applied_relations": applied,
        "applied_bottleneck_hints": applied_hints,
        "skipped_relations": skipped,
        "validation": validation,
        "bootstrap": bootstrap_result,
        "graph_stats_after": stats_after,
    }
