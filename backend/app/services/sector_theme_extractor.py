"""从上传研报/证据中抽取潜在新赛道主题。"""

from __future__ import annotations

import json
import re

from app.services.document_store import list_documents
from app.services.llm_client import chat_completion, is_llm_enabled, parse_json_response
from app.services.vector_store import search_documents, search_evidence
from app.services.graph_store import get_store

THEME_QUERIES = [
    "高景气 产业赛道 需求增长",
    "资本开支 扩产 产业链",
    "新兴行业 投资主题 瓶颈",
]

# 规则降级：常见产业主题词
_THEME_PATTERNS = [
    (r"(人形机器人|工业机器人)", "人形机器人", ["人形机器人", "谐波减速器", "丝杠"], ["人形机器人整机"]),
    (r"(低空经济|eVTOL|通航)", "低空经济", ["低空经济", "eVTOL", "无人机"], ["eVTOL飞行器"]),
    (r"(先进封装|CoWoS|Chiplet)", "先进封装", ["先进封装", "CoWoS", "封装基板"], ["CoWoS先进封装"]),
    (r"(光模块|EML|硅光)", "光通信", ["光模块", "EML", "硅光"], ["高速光模块"]),
    (r"(固态电池|锂电)", "新能源电池", ["固态电池", "锂电", "储能"], ["动力电池"]),
    (r"(AI算力|GPU|HBM)", "AI算力", ["算力", "GPU", "HBM", "光模块"], ["AI服务器"]),
]


def _gather_report_snippets(limit: int = 12) -> list[dict]:
    store = get_store()
    evidence = list(store.evidence.values())
    merged: dict[str, dict] = {}
    for q in THEME_QUERIES:
        for h in search_evidence(q, evidence, top_k=4):
            rid = h.get("ref_id")
            if rid:
                merged[rid] = h
        for h in search_documents(q, top_k=4):
            rid = h.get("ref_id")
            if rid:
                merged[rid] = h

    from app.services.ods_service import list_ods_research_reports

    for report in list_ods_research_reports(limit=8):
        rid = report.get("report_id")
        title = report.get("title") or ""
        if rid and title and rid not in merged:
            merged[rid] = {
                "ref_id": rid,
                "source_ref": title,
                "excerpt": title[:200],
                "source_type": "ods_research_report",
            }

    for doc in list_documents()[:8]:
        rid = doc.get("doc_id")
        ref = doc.get("source_ref") or doc.get("filename") or ""
        if rid and ref and rid not in merged:
            merged[rid] = {
                "ref_id": rid,
                "source_ref": ref,
                "excerpt": ref[:200],
                "source_type": "uploaded_document",
            }

    return list(merged.values())[:limit]


def _rule_extract_themes(snippets: list[dict]) -> list[dict]:
    blob = " ".join(f"{s.get('source_ref', '')} {s.get('excerpt', '')}" for s in snippets)
    themes: dict[str, dict] = {}
    for pattern, name, keywords, terminals in _THEME_PATTERNS:
        if not re.search(pattern, blob):
            continue
        refs = [
            {"ref_id": s.get("ref_id"), "excerpt": (s.get("excerpt") or "")[:100]}
            for s in snippets
            if re.search(pattern, f"{s.get('source_ref', '')} {s.get('excerpt', '')}")
        ][:2]
        themes[name] = {
            "sector_name": name,
            "sector_id": None,
            "keywords": keywords,
            "terminal_products": terminals,
            "source": "report_rule",
            "confidence": "medium" if refs else "low",
            "evidence_refs": refs,
            "mention_count": len(refs),
        }
    return list(themes.values())


def _llm_extract_themes(snippets: list[dict], focus: str | None) -> list[dict] | None:
    if not snippets:
        return []
    system = (
        "从研报摘录中识别潜在高景气产业赛道主题。禁止股价预测。\n"
        "输出 JSON: {\"themes\":[{\"sector_name\":\"\",\"keywords\":[],"
        "\"terminal_products\":[],\"confidence\":\"high|medium|low\","
        "\"evidence_refs\":[{\"ref_id\":\"\",\"excerpt\":\"\"}]}]}"
    )
    user = json.dumps(
        {"focus": focus, "snippets": snippets[:10]},
        ensure_ascii=False,
        indent=2,
    )
    raw = chat_completion(system, user, temperature=0.2)
    if not raw:
        return None
    parsed = parse_json_response(raw)
    if not parsed:
        return None
    out = []
    for t in parsed.get("themes", []):
        if t.get("sector_name"):
            t["sector_id"] = None
            t["source"] = "report_llm"
            out.append(t)
    return out


def extract_sector_themes_from_reports(focus: str | None = None) -> dict:
    """扫描已上传研报与证据，抽取赛道主题候选。"""
    docs = list_documents()
    snippets = _gather_report_snippets()
    themes: list[dict] = []

    if is_llm_enabled() and snippets:
        llm_themes = _llm_extract_themes(snippets, focus)
        if llm_themes is not None:
            themes = llm_themes

    if not themes:
        themes = _rule_extract_themes(snippets)

    return {
        "uploaded_doc_count": len(docs),
        "snippet_count": len(snippets),
        "themes": themes,
        "extraction_mode": "llm" if is_llm_enabled() and themes and themes[0].get("source") == "report_llm" else "rule",
    }
