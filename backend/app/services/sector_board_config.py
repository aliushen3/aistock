"""赛道成分股同步配置 — 存 OntSector.attrs.constituent_config，JSON 仅作内置种子 fallback。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ontology import pg_store

ATTR_KEY = "constituent_config"
LEGACY_JSON_PATH = Path(__file__).resolve().parents[1] / "data" / "sector_boards.json"


def _normalize_config(raw: dict | None) -> dict | None:
    if not raw or not isinstance(raw, dict):
        return None
    boards = raw.get("boards")
    if not isinstance(boards, list):
        boards = []
    boards_out = []
    for b in boards:
        if not isinstance(b, dict):
            continue
        name = (b.get("name") or "").strip()
        if not name:
            continue
        btype = (b.get("type") or "concept").strip().lower()
        if btype not in ("concept", "industry"):
            btype = "concept"
        boards_out.append({"type": btype, "name": name})
    keywords = raw.get("product_keywords") or {}
    if not isinstance(keywords, dict):
        keywords = {}
    keywords_out: dict[str, list[str]] = {}
    for pid, kws in keywords.items():
        if not pid:
            continue
        if isinstance(kws, str):
            kws = [kws]
        if not isinstance(kws, list):
            continue
        cleaned = [str(k).strip() for k in kws if str(k).strip()]
        if cleaned:
            keywords_out[str(pid)] = cleaned
    default_id = raw.get("default_product_id")
    default_id = str(default_id).strip() if default_id else None
    if not boards_out and not keywords_out and not default_id:
        return None
    return {
        "boards": boards_out,
        "default_product_id": default_id,
        "product_keywords": keywords_out,
    }


def _load_legacy_json(sector_id: str) -> dict | None:
    if not LEGACY_JSON_PATH.exists():
        return None
    with open(LEGACY_JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    raw = data.get(sector_id)
    return _normalize_config(raw) if isinstance(raw, dict) else None


def _read_from_db(sector_id: str) -> dict | None:
    if not pg_store.is_db_enabled():
        return None
    from sqlalchemy import select

    from app.db.models import OntSector
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        row = db.get(OntSector, sector_id)
        if row is None:
            return None
        attrs = row.attrs or {}
        return _normalize_config(attrs.get(ATTR_KEY))
    finally:
        db.close()


def get_sector_board_config(sector_id: str) -> dict | None:
    """优先 DB，其次内置 JSON 种子（只读 fallback）。"""
    cfg = _read_from_db(sector_id)
    if cfg:
        return cfg
    return _load_legacy_json(sector_id)


def get_sector_board_config_meta(sector_id: str) -> dict[str, Any]:
    db_cfg = _read_from_db(sector_id)
    if db_cfg:
        source = "db"
        config = db_cfg
    else:
        legacy = _load_legacy_json(sector_id)
        if legacy:
            source = "json_seed"
            config = legacy
        else:
            source = "none"
            config = {"boards": [], "default_product_id": None, "product_keywords": {}}
    from app.services.graph_store import get_store

    store = get_store()
    products = [
        {"id": p["id"], "name": p.get("name", p["id"])}
        for p in store.list_products(sector_id)
    ]
    return {
        "sector_id": sector_id,
        "source": source,
        "config": config,
        "available_products": products,
        "note": "配置保存在 Sector.attrs.constituent_config；内置 sector_boards.json 仅作种子 fallback",
    }


def save_sector_board_config(sector_id: str, config: dict) -> dict:
    if not pg_store.is_db_enabled():
        raise ValueError("数据库未启用，无法保存成分股配置")
    normalized = _normalize_config(config)
    if normalized is None:
        raise ValueError("配置无效：至少需配置一个东财板块（boards）")
    if not normalized.get("boards"):
        raise ValueError("至少配置一个东财板块（type + name）")
    from app.db.models import OntSector
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        row = db.get(OntSector, sector_id)
        if row is None:
            raise ValueError(f"赛道不存在: {sector_id}")
        attrs = dict(row.attrs or {})
        attrs[ATTR_KEY] = normalized
        row.attrs = attrs
        db.commit()
    finally:
        db.close()
    return get_sector_board_config_meta(sector_id)


def import_legacy_json_to_db(sector_id: str) -> dict:
    legacy = _load_legacy_json(sector_id)
    if not legacy:
        raise ValueError(f"内置种子中无赛道 {sector_id} 的配置")
    if not pg_store.is_db_enabled():
        raise ValueError("数据库未启用")
    pg_store.update_sector_property(sector_id, ATTR_KEY, legacy)
    return get_sector_board_config_meta(sector_id)
