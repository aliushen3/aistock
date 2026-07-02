"""产业链知识图谱存储抽象。

一期 MVP 使用内存实现（从 JSON 种子文件加载），便于无依赖跑通流程；
二期可替换为 Neo4j 实现，对外接口保持不变（见 docs/05-serenity-algorithm.md）。

边语义：UPSTREAM_OF 表示 source 是 target 的上游，即
    source -[:UPSTREAM_OF]-> target
因此「求某产品的上游」= 收集所有 target==该产品 的边的 source。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed_ai_compute.json"


class InMemoryGraphStore:
    def __init__(self, seed: dict):
        self.meta: dict = seed.get("meta", {})
        self.sectors: dict[str, dict] = {s["id"]: s for s in seed.get("sectors", [])}
        self.products: dict[str, dict] = {p["id"]: p for p in seed.get("products", [])}
        self.companies: dict[str, dict] = {c["code"]: c for c in seed.get("companies", [])}
        self.evidence: dict[str, dict] = {e["id"]: e for e in seed.get("evidence", [])}
        self.relations: list[dict] = seed.get("relations", [])

        # 邻接索引
        self._upstream_of: dict[str, list[str]] = {}   # product -> 其上游产品列表
        self._downstream_of: dict[str, list[str]] = {}  # product -> 其下游产品列表
        for rel in self.relations:
            if rel.get("type") != "UPSTREAM_OF":
                continue
            up, down = rel["source"], rel["target"]
            self._upstream_of.setdefault(down, []).append(up)
            self._downstream_of.setdefault(up, []).append(down)

        # company-by-product 索引
        self._producers: dict[str, list[str]] = {}
        for code, c in self.companies.items():
            for pid in c.get("produces", []):
                self._producers.setdefault(pid, []).append(code)

    # ---- 基础查询 ----
    def get_sector(self, sector_id: str) -> dict | None:
        return self.sectors.get(sector_id)

    def list_sectors(self) -> list[dict]:
        return list(self.sectors.values())

    def get_product(self, product_id: str) -> dict | None:
        return self.products.get(product_id)

    def list_products(self, sector_id: str | None = None) -> list[dict]:
        if sector_id is None:
            return list(self.products.values())
        return [p for p in self.products.values() if p.get("sector_id") == sector_id]

    def get_company(self, code: str) -> dict | None:
        return self.companies.get(code)

    def companies_producing(self, product_id: str) -> list[dict]:
        return [self.companies[c] for c in self._producers.get(product_id, [])]

    def upstream_of(self, product_id: str) -> list[str]:
        return self._upstream_of.get(product_id, [])

    def get_evidence(self, ev_id: str) -> dict | None:
        return self.evidence.get(ev_id)

    def resolve_evidence(self, ev_ids: list[str]) -> list[dict]:
        return [self.evidence[e] for e in ev_ids if e in self.evidence]

    # ---- 子图（供 G6 可视化）----
    def sector_subgraph(self, sector_id: str) -> dict:
        nodes, edges = [], []
        prods = self.list_products(sector_id)
        prod_ids = {p["id"] for p in prods}
        from app.ontology.property_overlays import merge_product
        from app.services.freshness import product_freshness

        for p in prods:
            merged = merge_product(p, p["id"]) or p
            nodes.append(
                {
                    "id": p["id"],
                    "label": p["name"],
                    "type": "product",
                    "layer": p["layer"],
                    "bottleneck_status": merged.get("bottleneck_status", "none"),
                    "serenity_niche": merged.get("serenity_niche", False),
                    "freshness": product_freshness(merged)["freshness"],
                }
            )
        for rel in self.relations:
            if rel.get("type") != "UPSTREAM_OF":
                continue
            if rel["source"] in prod_ids and rel["target"] in prod_ids:
                edges.append(
                    {"source": rel["source"], "target": rel["target"], "type": "UPSTREAM_OF"}
                )
        # 公司节点（关联到其生产的产品）
        for code, c in self.companies.items():
            linked = [pid for pid in c.get("produces", []) if pid in prod_ids]
            if not linked:
                continue
            nodes.append(
                {
                    "id": code,
                    "label": c["name"],
                    "type": "company",
                    "market_cap_billion": c.get("market_cap_billion"),
                }
            )
            for pid in linked:
                edges.append({"source": code, "target": pid, "type": "PRODUCES"})
        return {"sector_id": sector_id, "nodes": nodes, "edges": edges}

    # ---- 反向溯源（Serenity 用）----
    def reverse_paths(
        self, terminal_id: str, min_hops: int, max_hops: int
    ) -> list[list[str]]:
        """从终端产品沿 UPSTREAM_OF 反向遍历，返回深度在 [min_hops, max_hops] 的路径。

        每条路径是产品 id 列表：[terminal, ..., leaf_upstream]（含中间节点）。
        """
        results: list[list[str]] = []

        def dfs(node: str, path: list[str]):
            depth = len(path) - 1  # 已走的跳数
            if depth >= min_hops:
                results.append(list(path))
            if depth >= max_hops:
                return
            for up in self.upstream_of(node):
                if up in path:  # 防环
                    continue
                path.append(up)
                dfs(up, path)
                path.pop()

        dfs(terminal_id, [terminal_id])
        return results

    def _rebuild_adjacency(self) -> None:
        self._upstream_of = {}
        self._downstream_of = {}
        for rel in self.relations:
            if rel.get("type") != "UPSTREAM_OF":
                continue
            up, down = rel["source"], rel["target"]
            self._upstream_of.setdefault(down, []).append(up)
            self._downstream_of.setdefault(up, []).append(down)

    def add_upstream_link(self, source_id: str, target_id: str) -> bool:
        key = {"source": source_id, "target": target_id, "type": "UPSTREAM_OF"}
        if key in self.relations:
            return False
        self.relations.append(key)
        self._rebuild_adjacency()
        return True

    def remove_upstream_link(self, source_id: str, target_id: str) -> bool:
        before = len(self.relations)
        self.relations = [
            r
            for r in self.relations
            if not (
                r.get("type") == "UPSTREAM_OF"
                and r["source"] == source_id
                and r["target"] == target_id
            )
        ]
        if len(self.relations) == before:
            return False
        self._rebuild_adjacency()
        return True


class HybridGraphStore(InMemoryGraphStore):
    """内存权威数据 + Neo4j 遍历读路径。"""

    def upstream_of(self, product_id: str) -> list[str]:
        from app.services import neo4j_traversal

        neo = neo4j_traversal.upstream_of(product_id)
        if neo is not None:
            return neo
        return super().upstream_of(product_id)

    def reverse_paths(
        self, terminal_id: str, min_hops: int, max_hops: int
    ) -> list[list[str]]:
        from app.services import neo4j_traversal

        neo = neo4j_traversal.reverse_paths(terminal_id, min_hops, max_hops)
        if neo is not None:
            return neo
        return super().reverse_paths(terminal_id, min_hops, max_hops)

    @property
    def traversal_backend(self) -> str:
        from app.ontology.graph_projector import is_neo4j_available

        return "neo4j" if is_neo4j_available() else "memory"


def sector_company_codes(sector_id: str) -> list[str]:
    """赛道下经 Product→Company 关联的真实 A 股代码（去重、排序）。"""
    from app.adapters.market._utils import is_real_a_share_code, normalize_display_code

    store = get_store()
    seen: dict[str, None] = {}
    for product in store.list_products(sector_id):
        for company in store.companies_producing(product["id"]):
            code = normalize_display_code(company["code"])
            if is_real_a_share_code(code):
                seen.setdefault(code, None)
    return sorted(seen.keys())


_use_db_seed = False


def set_store_from_db(enabled: bool) -> None:
    global _use_db_seed
    _use_db_seed = enabled
    invalidate_store_cache()


def invalidate_store_cache() -> None:
    get_store.cache_clear()


@lru_cache(maxsize=1)
def get_store() -> HybridGraphStore:
    if _use_db_seed:
        from app.ontology.seed_loader import build_seed_dict_from_db

        seed = build_seed_dict_from_db()
    else:
        from app.config import LOAD_DEMO_SEED
        from app.ontology.seed_loader import EMPTY_SEED_DICT

        if LOAD_DEMO_SEED:
            with open(SEED_PATH, encoding="utf-8") as f:
                seed = json.load(f)
        else:
            seed = EMPTY_SEED_DICT
    return HybridGraphStore(seed)
