"""Serenity 逆向溯源 — 输出候选提示，需研究员确认。"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class TracePath:
    path_id: str
    node_ids: list[str]
    niche_product_id: str
    hop_count: int
    serenity_hint: float
    companies: list[dict] = field(default_factory=list)
    status: str = "pending_review"


def load_config() -> dict:
    path = Path(__file__).resolve().parents[2] / "config" / "serenity.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def passes_company_filter(company: dict, config: dict) -> bool:
    if company.get("market_cap", 0) >= config["max_market_cap_billion"]:
        return False
    if company.get("analyst_coverage", 99) >= config["max_analyst_coverage"]:
        return False
    if company.get("turnover_percentile", 1) >= config["max_turnover_percentile"]:
        return False
    return True


def serenity_reverse_trace(
    graph,  # Neo4j driver or adapter
    terminal_product_ids: list[str],
    sector_id: str,
) -> list[TracePath]:
    """
    从终端产品反向遍历上游，筛选 Serenity 候选路径。
    graph 参数一期对接 Neo4j，当前返回空列表占位。
    """
    config = load_config()
    _ = (graph, terminal_product_ids, sector_id, config)
    return []
