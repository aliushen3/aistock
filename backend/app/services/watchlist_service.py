"""动态观察清单 — 研报主题 + Ontology 赛道 + ODS/上传元数据（C7，去除写死清单）。"""

from __future__ import annotations

from collections import Counter

from app.ontology.object_store import list_sectors
from app.services.document_store import list_documents
from app.services.graph_store import get_store
from app.services.sector_recommendations import list_recommendations
from app.services.sector_theme_extractor import extract_sector_themes_from_reports

_SOURCE_PRIORITY = {
    "focus": 0,
    "report_llm": 1,
    "report_rule": 2,
    "report": 2,
    "proposal": 3,
    "upload": 4,
    "ods": 5,
    "ontology": 6,
}

_cache: dict | None = None


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def _match_sector_id_by_name(name: str) -> str | None:
    norm = _normalize_name(name)
    for sector in list_sectors():
        if _normalize_name(sector["name"]) == norm:
            return sector["id"]
    return None


def _sector_row_to_watch_item(sector: dict) -> dict:
    store = get_store()
    products = store.list_products(sector["id"])
    terminals = [p["name"] for p in products if p.get("layer") == "terminal"]
    product_names = [p["name"] for p in products]
    keywords = list(dict.fromkeys([sector["name"], *terminals, *product_names[:8]]))
    return {
        "sector_name": sector["name"],
        "sector_id": sector["id"],
        "keywords": keywords,
        "terminal_products": terminals or product_names[:2] or [sector["name"]],
        "source": "ontology",
        "status": sector.get("status"),
        "human_confirmed": sector.get("human_confirmed", False),
    }


def _focus_item(focus: str | None) -> dict | None:
    if not focus or not focus.strip():
        return None
    name = focus.strip()
    return {
        "sector_name": name,
        "sector_id": _match_sector_id_by_name(name),
        "keywords": list(dict.fromkeys([name, *name.replace("，", " ").replace(",", " ").split()])),
        "terminal_products": [],
        "source": "focus",
    }


def _themes_from_upload_metadata() -> list[dict]:
    docs = list_documents()
    by_sector: dict[str, list[dict]] = {}
    for doc in docs:
        sid = doc.get("sector_id")
        if sid:
            by_sector.setdefault(sid, []).append(doc)

    store = get_store()
    items: list[dict] = []
    for sid, sector_docs in by_sector.items():
        sector = store.get_sector(sid)
        if sector is None:
            continue
        refs = [
            {
                "ref_id": doc["doc_id"],
                "excerpt": (doc.get("source_ref") or doc.get("filename") or "")[:100],
            }
            for doc in sector_docs[:3]
        ]
        items.append(
            {
                "sector_name": sector["name"],
                "sector_id": sid,
                "keywords": [sector["name"]],
                "terminal_products": [],
                "source": "upload",
                "evidence_refs": refs,
                "doc_count": len(sector_docs),
            }
        )
    return items


def _themes_from_ods_reports() -> list[dict]:
    from app.services.ods_service import list_ods_research_reports

    reports = list_ods_research_reports(limit=50)
    if not reports:
        return []

    store = get_store()
    by_sector: dict[str, list[dict]] = {}
    for report in reports:
        sid = report.get("sector_id")
        if sid:
            by_sector.setdefault(sid, []).append(report)

    items: list[dict] = []
    for sid, sector_reports in by_sector.items():
        sector = store.get_sector(sid)
        if sector is None:
            continue
        refs = [
            {"ref_id": report["report_id"], "excerpt": (report.get("title") or "")[:100]}
            for report in sector_reports[:3]
        ]
        items.append(
            {
                "sector_name": sector["name"],
                "sector_id": sid,
                "keywords": [sector["name"], *(report.get("title", "")[:20] for report in sector_reports[:1])],
                "terminal_products": [],
                "source": "ods",
                "evidence_refs": refs,
                "report_count": len(sector_reports),
            }
        )
    return items


def _themes_from_proposals() -> list[dict]:
    proposals = list_recommendations(status="proposed", limit=20)
    items: list[dict] = []
    for prop in proposals:
        name = prop.get("sector_name")
        if not name:
            continue
        items.append(
            {
                "sector_name": name,
                "sector_id": prop.get("sector_id"),
                "keywords": [name],
                "terminal_products": prop.get("terminal_products") or [],
                "source": "proposal",
                "rec_id": prop.get("rec_id"),
                "beta_score": prop.get("beta_score"),
            }
        )
    return items


def _merge_items(*groups: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []

    for group in groups:
        for item in group:
            name = item.get("sector_name")
            if not name:
                continue
            key = _normalize_name(name)
            if key not in merged:
                merged[key] = dict(item)
                order.append(key)
                continue

            existing = merged[key]
            if not existing.get("sector_id") and item.get("sector_id"):
                existing["sector_id"] = item["sector_id"]
            existing["keywords"] = list(
                dict.fromkeys(existing.get("keywords", []) + item.get("keywords", []))
            )
            existing["terminal_products"] = list(
                dict.fromkeys(existing.get("terminal_products", []) + item.get("terminal_products", []))
            )
            refs = existing.get("evidence_refs", []) + item.get("evidence_refs", [])
            existing["evidence_refs"] = refs[:5]
            if _SOURCE_PRIORITY.get(item.get("source", ""), 99) < _SOURCE_PRIORITY.get(
                existing.get("source", ""), 99
            ):
                existing["source"] = item["source"]
            if item.get("confidence"):
                existing["confidence"] = item["confidence"]

    def sort_key(key: str) -> tuple:
        item = merged[key]
        return (_SOURCE_PRIORITY.get(item.get("source", ""), 99), item["sector_name"])

    return [merged[key] for key in sorted(order, key=sort_key)]


def invalidate_watchlist_cache() -> None:
    global _cache
    _cache = None


def build_dynamic_watchlist(focus: str | None = None, refresh: bool = False) -> dict:
    """构建动态观察清单：研报抽取 + 提案 + 上传/ODS 元数据 + Ontology 已有赛道。"""
    global _cache
    cache_key = focus or ""
    if not refresh and _cache and _cache.get("focus") == cache_key:
        return _cache["result"]

    theme_result = extract_sector_themes_from_reports(focus=focus)
    report_themes = theme_result.get("themes", [])

    groups: list[list[dict]] = []
    focus_row = _focus_item(focus)
    if focus_row:
        groups.append([focus_row])
    groups.extend(
        [
            report_themes,
            _themes_from_proposals(),
            _themes_from_upload_metadata(),
            _themes_from_ods_reports(),
            [_sector_row_to_watch_item(s) for s in list_sectors()],
        ]
    )
    watchlist = _merge_items(*groups)
    source_counts = dict(Counter(item.get("source", "unknown") for item in watchlist))

    result = {
        "dynamic": True,
        "watchlist": watchlist,
        "watchlist_count": len(watchlist),
        "source_counts": source_counts,
        "report_themes": theme_result,
    }
    _cache = {"focus": cache_key, "result": result}
    return result


def get_watchlist(focus: str | None = None, refresh: bool = False) -> list[dict]:
    return build_dynamic_watchlist(focus=focus, refresh=refresh)["watchlist"]


def list_watchlist_sector_ids(focus: str | None = None) -> list[str]:
    """返回观察清单中已有 sector_id 的赛道列表；空则回退 Ontology 全部赛道。"""
    ids: list[str] = []
    seen: set[str] = set()
    for item in get_watchlist(focus=focus):
        sid = item.get("sector_id")
        if sid and sid not in seen:
            seen.add(sid)
            ids.append(sid)
    if ids:
        return ids
    store = get_store()
    return [s["id"] for s in store.list_sectors()]
