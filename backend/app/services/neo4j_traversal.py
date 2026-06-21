"""Neo4j 图遍历读路径 — 多跳查询走图数据库。"""

from __future__ import annotations

import logging

from app.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from app.ontology.graph_projector import is_neo4j_available

logger = logging.getLogger(__name__)


def _driver():
    from neo4j import GraphDatabase

    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def upstream_of(product_id: str) -> list[str] | None:
    if not is_neo4j_available():
        return None
    try:
        with _driver().session() as session:
            result = session.run(
                """
                MATCH (up:Product)-[:UPSTREAM_OF]->(p:Product {id: $pid})
                RETURN up.id AS id
                """,
                pid=product_id,
            )
            return [r["id"] for r in result]
    except Exception as e:
        logger.warning("Neo4j upstream_of 失败: %s", e)
        return None


def reverse_paths(terminal_id: str, min_hops: int, max_hops: int) -> list[list[str]] | None:
    if not is_neo4j_available():
        return None
    try:
        with _driver().session() as session:
            result = session.run(
                """
                MATCH path = (leaf:Product)-[:UPSTREAM_OF*1..4]->(t:Product {id: $tid})
                WHERE length(path) >= $min_h AND length(path) <= $max_h
                RETURN [n IN nodes(path) | n.id] AS ids
                LIMIT 200
                """,
                tid=terminal_id,
                min_h=min_hops,
                max_h=max_hops,
            )
            paths = []
            for r in result:
                ids = list(r["ids"])
                ids.reverse()
                paths.append(ids)
            return paths
    except Exception as e:
        logger.warning("Neo4j reverse_paths 失败: %s", e)
        return None


def sector_upstream_stats(sector_id: str) -> dict | None:
    """赛道内上游关系统计（供健康检查）。"""
    if not is_neo4j_available():
        return None
    try:
        with _driver().session() as session:
            row = session.run(
                """
                MATCH (p:Product)-[:BELONGS_TO]->(s:Sector {id: $sid})
                OPTIONAL MATCH (up:Product)-[:UPSTREAM_OF]->(p)
                RETURN count(DISTINCT p) AS products, count(up) AS upstream_edges
                """,
                sid=sector_id,
            ).single()
            return {"products": row["products"], "upstream_edges": row["upstream_edges"]}
    except Exception as e:
        logger.warning("Neo4j sector stats 失败: %s", e)
        return None
