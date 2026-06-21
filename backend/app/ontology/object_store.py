"""Ontology 对象存储 — 一期内存实现，合并种子数据与 Action 写回覆盖。"""

from __future__ import annotations

from app.ontology.property_overlays import merge_product, merge_sector, set_product_property, set_sector_property
from app.services.candidate_pool import build_pool, get_state, set_state
from app.services.graph_store import get_store


def make_candidate_entry_id(sector_id: str, mode: str, stock_code: str) -> str:
    return f"{sector_id}:{mode}:{stock_code}"


def parse_candidate_entry_id(entry_id: str) -> tuple[str, str, str]:
    parts = entry_id.split(":", 2)
    if len(parts) != 3:
        raise ValueError(f"无效的 CandidatePoolEntry id: {entry_id}")
    return parts[0], parts[1], parts[2]


def get_sector(sector_id: str) -> dict | None:
    return merge_sector(get_store().get_sector(sector_id), sector_id)


def list_sectors() -> list[dict]:
    return [get_sector(s["id"]) for s in get_store().list_sectors() if get_sector(s["id"])]


def get_product(product_id: str) -> dict | None:
    return merge_product(get_store().get_product(product_id), product_id)


def set_object_property(object_type: str, object_id: str, property_name: str, value) -> None:
    if object_type == "Sector":
        set_sector_property(object_id, property_name, value)
    elif object_type == "Product":
        set_product_property(object_id, property_name, value)
    else:
        raise ValueError(f"不支持直接设置属性: {object_type}")


def get_candidate_entry(entry_id: str) -> dict | None:
    sector_id, mode, stock_code = parse_candidate_entry_id(entry_id)
    store = get_store()
    if store.get_sector(sector_id) is None:
        return None
    pool = {it["stock_code"]: it for it in build_pool(store, sector_id, mode)}
    if stock_code not in pool:
        return None
    item = pool[stock_code]
    return {
        "entry_id": entry_id,
        "stock_code": stock_code,
        "name": item.get("name"),
        "sector_id": sector_id,
        "mode": mode,
        "status": get_state(sector_id, mode, stock_code),
        "priority": item.get("priority"),
        "hint_score": item.get("hint_score"),
        "product_name": item.get("product_name"),
        "rationale": item.get("rationale"),
        "edge_assessment": item.get("edge_assessment"),
        "value_capture": item.get("value_capture"),
        "bear_status": item.get("bear_status", "none"),
    }


def update_candidate_entry(entry_id: str, status: str, reason: str, operator: str) -> dict:
    sector_id, mode, stock_code = parse_candidate_entry_id(entry_id)
    set_state(sector_id, mode, stock_code, status, reason, operator)
    entry = get_candidate_entry(entry_id)
    if entry is None:
        raise ValueError(f"候选条目不存在: {entry_id}")
    return entry


def get_research_report(report_id: str) -> dict | None:
    from app.ontology import pg_store

    if pg_store.is_db_enabled():
        return pg_store.get_report(report_id)
    from app.services.report import _report_store

    return _report_store.get(report_id)


def update_research_report_status(report_id: str, status: str, review: dict | None = None) -> dict | None:
    from app.ontology import pg_store

    if pg_store.is_db_enabled():
        return pg_store.update_report_status(report_id, status, review)
    from app.services.report import _report_store

    report = _report_store.get(report_id)
    if report is None:
        return None
    report["status"] = status
    if review:
        report["review"] = review
    return report


def query_object_set(name: str, filter_extra: dict | None = None) -> list[dict]:
    """按 object_sets.yaml 定义查询对象集。"""
    from app.ontology.registry import ontology_registry

    spec = ontology_registry.get_object_set(name)
    if spec is None:
        raise ValueError(f"未知 Object Set: {name}")

    object_type = spec["object_type"]
    filt = {**spec.get("filter", {}), **(filter_extra or {})}
    items: list[dict] = []

    if object_type == "Sector":
        for s in list_sectors():
            if _match_filter(s, filt):
                items.append({"object_type": "Sector", "id": s["id"], **s})
    elif object_type == "Product":
        from app.services.freshness import product_freshness

        for p in get_store().list_products():
            merged = get_product(p["id"])
            if not merged:
                continue
            merged = {**merged, "freshness": product_freshness(merged)["freshness"]}
            if _match_filter(merged, filt):
                items.append({"object_type": "Product", "id": p["id"], **merged})
    elif object_type == "CandidatePoolEntry":
        sector_id = (filter_extra or {}).get("sector_id", "sector_ai_compute")
        mode = filt.get("mode", "fusion")
        store = get_store()
        for it in build_pool(store, sector_id, mode):
            entry_id = make_candidate_entry_id(sector_id, mode, it["stock_code"])
            entry = get_candidate_entry(entry_id)
            if entry and _match_filter(entry, filt):
                items.append({"object_type": "CandidatePoolEntry", **entry})
    elif object_type == "SectorRecommendation":
        from app.services.sector_recommendations import list_recommendations

        status = filt.get("status", "proposed")
        for rec in list_recommendations(status=status, limit=50):
            if _match_filter(rec, filt):
                items.append({"object_type": "SectorRecommendation", **rec})
    elif object_type == "BottleneckRecommendation":
        from app.services.bottleneck_recommendations import list_recommendations as list_bn

        status = filt.get("status", "proposed")
        sector_id = (filter_extra or {}).get("sector_id")
        for rec in list_bn(sector_id=sector_id, status=status, limit=50):
            if _match_filter(rec, filt):
                items.append({"object_type": "BottleneckRecommendation", **rec})
    elif object_type == "SerenityRecommendation":
        from app.services.serenity_recommendations import list_recommendations as list_ser

        status = filt.get("status", "proposed")
        sector_id = (filter_extra or {}).get("sector_id")
        for rec in list_ser(sector_id=sector_id, status=status, limit=50):
            if _match_filter(rec, filt):
                items.append({"object_type": "SerenityRecommendation", **rec})
    elif object_type == "BearCase":
        from app.services import bearcase_store

        sector_id = (filter_extra or {}).get("sector_id")
        for b in bearcase_store.list_bear_cases(
            sector_id=sector_id,
            severity=filt.get("severity"),
            status=filt.get("rebuttal_status"),
            limit=100,
        ):
            items.append({"object_type": "BearCase", "id": b["bear_id"], **b})
    return items


def _match_filter(obj: dict, filt: dict) -> bool:
    for key, expected in filt.items():
        # sector_id / mode 为路由参数（候选池按 mode 构建，天然一致），非对象属性过滤
        if key in ("sector_id", "mode"):
            continue
        val = obj.get(key)
        if isinstance(expected, dict) and "in" in expected:
            if val not in expected["in"]:
                return False
        elif val != expected:
            return False
    return True
