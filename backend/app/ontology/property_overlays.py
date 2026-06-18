"""对象属性覆盖层 — 供 Ontology Action 写回，避免 object_store 与 candidate_pool 循环依赖。"""

from __future__ import annotations

_sector_overrides: dict[str, dict] = {}
_product_overrides: dict[str, dict] = {}


def set_sector_property(sector_id: str, key: str, value) -> None:
    _sector_overrides.setdefault(sector_id, {})[key] = value
    from app.ontology import pg_store

    if pg_store.is_db_enabled():
        pg_store.update_sector_property(sector_id, key, value)


def set_product_property(product_id: str, key: str, value) -> None:
    _product_overrides.setdefault(product_id, {})[key] = value
    from app.ontology import pg_store

    if pg_store.is_db_enabled():
        pg_store.update_product_property(product_id, key, value)


def merge_sector(base: dict | None, sector_id: str) -> dict | None:
    if base is None:
        return None
    return {**base, **_sector_overrides.get(sector_id, {})}


def merge_product(base: dict | None, product_id: str) -> dict | None:
    if base is None:
        return None
    return {**base, **_product_overrides.get(product_id, {})}


def clear_all() -> None:
    """测试用。"""
    _sector_overrides.clear()
    _product_overrides.clear()
