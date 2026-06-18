"""从 seed_ai_compute.json 导入 PostgreSQL Ontology 表。"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from app.db.models import (
    OntCompany,
    OntEvidence,
    OntLinkProduces,
    OntLinkUpstream,
    OntProduct,
    OntSector,
)
from app.db.session import SessionLocal

SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed_ai_compute.json"


def is_db_seeded() -> bool:
    db = SessionLocal()
    try:
        count = db.scalar(select(func.count()).select_from(OntSector))
        return (count or 0) > 0
    except Exception:
        return False
    finally:
        db.close()


def load_seed_if_empty() -> bool:
    if is_db_seeded():
        return False
    with open(SEED_PATH, encoding="utf-8") as f:
        seed = json.load(f)
    db = SessionLocal()
    try:
        for s in seed.get("sectors", []):
            db.add(
                OntSector(
                    id=s["id"],
                    name=s["name"],
                    status=s.get("status", "beta_candidate"),
                    demand_growth_hint=s.get("demand_growth_hint"),
                    human_confirmed=s.get("human_confirmed", False),
                    terminal_products=s.get("terminal_products", []),
                )
            )
        for p in seed.get("products", []):
            db.add(
                OntProduct(
                    id=p["id"],
                    name=p["name"],
                    layer=p["layer"],
                    sector_id=p["sector_id"],
                    expansion_cycle_months=p.get("expansion_cycle_months", 0),
                    cr4_concentration=p.get("cr4_concentration", 0),
                    tech_barrier_score=p.get("tech_barrier_score", 50),
                    supply_demand_score=p.get("supply_demand_score", 50),
                    cost_ratio=p.get("cost_ratio", 0),
                    substitution_difficulty=p.get("substitution_difficulty", "medium"),
                    overseas_dependence=p.get("overseas_dependence", "low"),
                    certification_months=p.get("certification_months", 0),
                    bottleneck_status=p.get("bottleneck_status", "none"),
                    serenity_niche=p.get("serenity_niche", False),
                    provenance_ids=p.get("provenance_ids", []),
                )
            )
        for c in seed.get("companies", []):
            db.add(
                OntCompany(
                    code=c["code"],
                    name=c["name"],
                    market_cap_billion=c.get("market_cap_billion"),
                    analyst_coverage=c.get("analyst_coverage"),
                    turnover_percentile=c.get("turnover_percentile"),
                    gross_margin=c.get("gross_margin"),
                    market_rank=c.get("market_rank"),
                    pe_percentile=c.get("pe_percentile"),
                    produces=c.get("produces", []),
                )
            )
        for rel in seed.get("relations", []):
            if rel.get("type") == "UPSTREAM_OF":
                db.add(OntLinkUpstream(source_id=rel["source"], target_id=rel["target"]))
        for c in seed.get("companies", []):
            for pid in c.get("produces", []):
                db.add(OntLinkProduces(company_code=c["code"], product_id=pid))
        for e in seed.get("evidence", []):
            db.add(
                OntEvidence(
                    id=e["id"],
                    source_type=e["source_type"],
                    source_ref=e["source_ref"],
                    excerpt=e["excerpt"],
                )
            )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def build_seed_dict_from_db() -> dict:
    """从 PostgreSQL 构建与 JSON 种子相同结构的 dict，供 InMemoryGraphStore 使用。"""
    db = SessionLocal()
    try:
        sectors = [
            {
                "id": s.id,
                "name": s.name,
                "status": s.status,
                "demand_growth_hint": s.demand_growth_hint,
                "human_confirmed": s.human_confirmed,
                "terminal_products": s.terminal_products or [],
                **(s.attrs or {}),
            }
            for s in db.scalars(select(OntSector)).all()
        ]
        products = [
            {
                "id": p.id,
                "name": p.name,
                "layer": p.layer,
                "sector_id": p.sector_id,
                "expansion_cycle_months": p.expansion_cycle_months,
                "cr4_concentration": p.cr4_concentration,
                "tech_barrier_score": p.tech_barrier_score,
                "supply_demand_score": p.supply_demand_score,
                "cost_ratio": p.cost_ratio,
                "substitution_difficulty": p.substitution_difficulty,
                "overseas_dependence": p.overseas_dependence,
                "certification_months": p.certification_months,
                "bottleneck_status": p.bottleneck_status,
                "serenity_niche": p.serenity_niche,
                "provenance_ids": p.provenance_ids or [],
                **(p.attrs or {}),
            }
            for p in db.scalars(select(OntProduct)).all()
        ]
        companies = [
            {
                "code": c.code,
                "name": c.name,
                "market_cap_billion": c.market_cap_billion,
                "analyst_coverage": c.analyst_coverage,
                "turnover_percentile": c.turnover_percentile,
                "gross_margin": c.gross_margin,
                "market_rank": c.market_rank,
                "pe_percentile": c.pe_percentile,
                "produces": c.produces or [],
                **(c.attrs or {}),
            }
            for c in db.scalars(select(OntCompany)).all()
        ]
        relations = [
            {"source": l.source_id, "target": l.target_id, "type": "UPSTREAM_OF"}
            for l in db.scalars(select(OntLinkUpstream)).all()
        ]
        evidence = [
            {
                "id": e.id,
                "source_type": e.source_type,
                "source_ref": e.source_ref,
                "excerpt": e.excerpt,
            }
            for e in db.scalars(select(OntEvidence)).all()
        ]
        return {
            "meta": {"source": "postgresql"},
            "sectors": sectors,
            "products": products,
            "companies": companies,
            "relations": relations,
            "evidence": evidence,
        }
    finally:
        db.close()
