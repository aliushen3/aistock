"""图谱入图 — 真实板块成分股写入 Ontology。"""

from __future__ import annotations

from sqlalchemy import delete, select

from app.adapters.market._utils import is_real_a_share_code
from app.adapters.registry import get_constituent_adapter
from app.db.models import OntCompany, OntLinkProduces, OntProduct
from app.db.session import SessionLocal
from app.ontology import pg_store
from app.services.sector_board_config import get_sector_board_config


def map_company_to_products(
    company_name: str,
    product_rows: list[OntProduct],
    config: dict,
) -> list[str]:
    keywords_map = config.get("product_keywords") or {}
    matched: list[str] = []
    valid_ids = {p.id for p in product_rows}
    for pid, keywords in keywords_map.items():
        if pid not in valid_ids:
            continue
        if any(kw and kw in company_name for kw in keywords):
            matched.append(pid)
    if matched:
        return list(dict.fromkeys(matched))
    default_id = config.get("default_product_id")
    if default_id and default_id in valid_ids:
        return [default_id]
    terminals = [p.id for p in product_rows if p.layer == "terminal"]
    if terminals:
        return [terminals[0]]
    if product_rows:
        return [product_rows[0].id]
    return []


def _remove_demo_companies(db, product_ids: set[str]) -> int:
    if not product_ids:
        return 0
    demo_codes: list[str] = []
    for company in db.scalars(select(OntCompany)).all():
        if is_real_a_share_code(company.code):
            continue
        produces = set(company.produces or [])
        if produces & product_ids:
            demo_codes.append(company.code)
    if not demo_codes:
        return 0
    db.execute(delete(OntLinkProduces).where(OntLinkProduces.company_code.in_(demo_codes)))
    db.execute(delete(OntCompany).where(OntCompany.code.in_(demo_codes)))
    return len(demo_codes)


def _refresh_graph_projection() -> None:
    from app.ontology.graph_projector import project_graph
    from app.services.graph_store import invalidate_store_cache

    invalidate_store_cache()
    project_graph()


def sync_constituents(sector_id: str, adapter_name: str | None = None) -> dict:
    """拉取板块成分股，替换赛道内演示公司，写入 OntCompany + OntLinkProduces。"""
    if not pg_store.is_db_enabled():
        return {"status": "skipped", "sector_id": sector_id, "count": 0}

    config = get_sector_board_config(sector_id)
    if not config:
        raise ValueError(
            f"未配置成分股映射: {sector_id}，请在「知识抽取」或「系统与数据」页编辑 Sector 成分股配置"
        )

    boards = config.get("boards") or []
    if not boards:
        raise ValueError(f"赛道 {sector_id} 未配置 boards")

    adapter = get_constituent_adapter(adapter_name)
    merged: dict[str, dict] = {}
    for board in boards:
        btype = board.get("type", "concept")
        bname = board.get("name", "")
        if not bname:
            continue
        for rec in adapter.fetch_board_constituents(btype, bname):
            code = rec["stock_code"]
            if code not in merged:
                merged[code] = rec

    if not merged:
        return {
            "status": "ok",
            "adapter": adapter.name,
            "sector_id": sector_id,
            "count": 0,
            "companies_upserted": 0,
            "demo_removed": 0,
            "links_created": 0,
            "message": "未拉取到成分股，请检查板块名称或网络",
        }

    db = SessionLocal()
    try:
        product_rows = list(
            db.scalars(select(OntProduct).where(OntProduct.sector_id == sector_id)).all()
        )
        if not product_rows:
            raise ValueError(f"赛道 {sector_id} 尚无产品节点，请先确认 Ontology 结构")

        product_ids = {p.id for p in product_rows}
        demo_removed = _remove_demo_companies(db, product_ids)

        upserted = 0
        links_created = 0
        for rec in merged.values():
            code = rec["stock_code"]
            name = rec["name"]
            product_ids_for_company = map_company_to_products(name, product_rows, config)

            row = db.get(OntCompany, code)
            attrs = {"created_by": "constituent_sync", "board_name": rec.get("board_name")}
            if row is None:
                row = OntCompany(
                    code=code,
                    name=name,
                    market_cap_billion=rec.get("market_cap_billion"),
                    produces=product_ids_for_company,
                    attrs=attrs,
                )
                db.add(row)
                upserted += 1
            else:
                row.name = name
                if rec.get("market_cap_billion") is not None:
                    row.market_cap_billion = rec["market_cap_billion"]
                merged_produces = list(dict.fromkeys((row.produces or []) + product_ids_for_company))
                row.produces = merged_produces
                row.attrs = {**(row.attrs or {}), **attrs}
                upserted += 1

            db.execute(delete(OntLinkProduces).where(OntLinkProduces.company_code == code))
            for pid in product_ids_for_company:
                db.add(OntLinkProduces(company_code=code, product_id=pid))
                links_created += 1

        db.commit()
    finally:
        db.close()

    _refresh_graph_projection()

    real_count = len(merged)
    return {
        "status": "ok",
        "adapter": adapter.name,
        "sector_id": sector_id,
        "count": real_count,
        "companies_upserted": upserted,
        "demo_removed": demo_removed,
        "links_created": links_created,
    }


def ontology_company_stats() -> dict:
    """Ontology 公司统计（真实 vs 演示）。"""
    if not pg_store.is_db_enabled():
        return {"enabled": False}
    db = SessionLocal()
    try:
        companies = list(db.scalars(select(OntCompany)).all())
        real = [c for c in companies if is_real_a_share_code(c.code)]
        demo = [c for c in companies if not is_real_a_share_code(c.code)]
        return {
            "enabled": True,
            "total": len(companies),
            "real_codes": len(real),
            "demo_codes": len(demo),
        }
    finally:
        db.close()
