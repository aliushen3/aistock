"""PostgreSQL → Neo4j 图投影。"""

from __future__ import annotations

import logging

from app.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from app.services.graph_store import get_store

logger = logging.getLogger(__name__)

_neo4j_available: bool | None = None


def is_neo4j_available() -> bool:
    global _neo4j_available
    if _neo4j_available is not None:
        return _neo4j_available
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        driver.close()
        _neo4j_available = True
    except Exception as e:
        logger.warning("Neo4j 不可用，跳过图投影: %s", e)
        _neo4j_available = False
    return _neo4j_available


def project_graph() -> dict:
    """将当前图谱全量投影到 Neo4j。"""
    if not is_neo4j_available():
        return {"status": "skipped", "reason": "neo4j_unavailable"}

    from neo4j import GraphDatabase

    store = get_store()
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    sectors = store.list_sectors()
    products = store.list_products()
    companies = list(store.companies.values())

    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

        for s in sectors:
            session.run(
                """
                CREATE (s:Sector {
                    id: $id, name: $name, status: $status,
                    demand_growth_hint: $dgh, human_confirmed: $hc
                })
                """,
                id=s["id"],
                name=s["name"],
                status=s.get("status"),
                dgh=s.get("demand_growth_hint"),
                hc=s.get("human_confirmed", False),
            )

        for p in products:
            session.run(
                """
                CREATE (p:Product {
                    id: $id, name: $name, layer: $layer, sector_id: $sector_id,
                    bottleneck_status: $bs, serenity_niche: $sn,
                    expansion_cycle_months: $ecm, cr4_concentration: $cr4
                })
                WITH p
                MATCH (s:Sector {id: $sector_id})
                MERGE (p)-[:BELONGS_TO]->(s)
                """,
                id=p["id"],
                name=p["name"],
                layer=p.get("layer"),
                sector_id=p["sector_id"],
                bs=p.get("bottleneck_status", "none"),
                sn=p.get("serenity_niche", False),
                ecm=p.get("expansion_cycle_months"),
                cr4=p.get("cr4_concentration"),
            )

        for c in companies:
            session.run(
                """
                CREATE (c:Company {
                    code: $code, name: $name,
                    market_cap_billion: $mcap, analyst_coverage: $cov
                })
                """,
                code=c["code"],
                name=c["name"],
                mcap=c.get("market_cap_billion"),
                cov=c.get("analyst_coverage"),
            )
            for pid in c.get("produces", []):
                session.run(
                    """
                    MATCH (c:Company {code: $code}), (p:Product {id: $pid})
                    MERGE (c)-[:PRODUCES]->(p)
                    """,
                    code=c["code"],
                    pid=pid,
                )

        for rel in store.relations:
            if rel.get("type") != "UPSTREAM_OF":
                continue
            session.run(
                """
                MATCH (up:Product {id: $source}), (down:Product {id: $target})
                MERGE (up)-[:UPSTREAM_OF]->(down)
                """,
                source=rel["source"],
                target=rel["target"],
            )

    driver.close()
    return {
        "status": "ok",
        "sectors": len(sectors),
        "products": len(products),
        "companies": len(companies),
        "relations": len([r for r in store.relations if r.get("type") == "UPSTREAM_OF"]),
    }
