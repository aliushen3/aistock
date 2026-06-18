"""Serenity 逆向溯源 — 从终端赛道反向遍历上游，挖掘小众咽喉环节。

输出为候选提示清单，status=pending_review，需研究员确认后方可入池。
算法说明见 docs/05-serenity-algorithm.md。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class TracePath:
    path_id: str
    node_ids: list[str]
    node_names: list[str]
    niche_product_id: str
    niche_product_name: str
    hop_count: int
    serenity_hint: float
    prune_reasons: list[str] = field(default_factory=list)
    companies: list[dict] = field(default_factory=list)
    status: str = "pending_review"


def load_config() -> dict:
    path = Path(__file__).resolve().parents[2] / "config" / "serenity.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def passes_niche_filter(product: dict, config: dict) -> tuple[bool, str]:
    """产品层剪枝。返回 (是否保留, 原因)。"""
    if product.get("layer") == "terminal":
        return False, "终端环节，排除"
    if product.get("layer") not in ("material", "consumable"):
        return False, f"层级 {product.get('layer')} 非材料/耗材"
    if product.get("substitution_difficulty") == "low":
        return False, "存在低成本替代，剪枝"
    cost_ok = product.get("cost_ratio", 1.0) < config["max_cost_ratio"]
    sub_high = product.get("substitution_difficulty") == "high"
    if not (cost_ok or sub_high):
        return False, "成本占比不低且替代不难，非小众咽喉"
    return True, "小众刚需材料/耗材"


def passes_company_filter(company: dict, config: dict) -> tuple[bool, str]:
    """公司层剪枝（低拥挤、低覆盖、中小市值）。"""
    if company.get("market_cap_billion", 0) >= config["max_market_cap_billion"]:
        return False, "市值过大，非中小市值"
    if company.get("analyst_coverage", 99) >= config["max_analyst_coverage"]:
        return False, "机构覆盖过高，拥挤"
    if company.get("turnover_percentile", 1) >= config["max_turnover_percentile"]:
        return False, "成交额分位过高，拥挤"
    if company.get("market_rank", 99) <= config["exclude_top_n_by_cap"]:
        # 注：仅在该公司为赛道整体龙头时排除；小众环节龙头允许保留
        pass
    return True, "低拥挤低覆盖中小市值"


def _tier(value: float, tiers: list[tuple[float, float]]) -> float:
    for threshold, score in tiers:
        if value >= threshold:
            return float(score)
    return 0.0


def calc_serenity_hint(product: dict, company: dict, hop_count: int, config: dict) -> float:
    """Serenity 提示分（0-100，非投资决策分，仅供候选排序）。"""
    w = config["weights"]

    # 小众刚需匹配度：规则命中比例
    checks = [
        product.get("layer") in ("material", "consumable"),
        product.get("cost_ratio", 1.0) < config["max_cost_ratio"],
        product.get("substitution_difficulty") == "high",
        product.get("serenity_niche", False),
    ]
    niche_fit = sum(checks) / len(checks) * 100

    # 供给刚性：扩产周期 + 认证周期 + 海外依赖
    supply_rigidity = _tier(
        product.get("expansion_cycle_months", 0), [(24, 100), (18, 80), (12, 50), (0, 20)]
    )
    if product.get("overseas_dependence") == "high":
        supply_rigidity = min(100.0, supply_rigidity + 10)

    # 低关注：低覆盖 + 低拥挤
    coverage = company.get("analyst_coverage", 10)
    turnover = company.get("turnover_percentile", 1.0)
    low_attention = max(0.0, (5 - coverage) / 5) * 50 + (1 - turnover) * 50
    low_attention = min(100.0, low_attention)

    # 路径质量：跳数适中（3-4）为佳
    path_quality = 100.0 if hop_count in (config["min_hops"], config["max_hops"]) else 60.0

    total = (
        niche_fit * w["niche_fit"]
        + supply_rigidity * w["supply_rigidity"]
        + low_attention * w["low_attention"]
        + path_quality * w["path_quality"]
    )
    return round(total, 1)


def serenity_reverse_trace(
    store,
    terminal_product_ids: list[str],
    sector_id: str,
    config: dict | None = None,
) -> list[TracePath]:
    """从终端产品反向遍历上游，筛选 Serenity 候选路径。"""
    config = config or load_config()
    best_by_niche: dict[str, TracePath] = {}

    for terminal_id in terminal_product_ids:
        raw_paths = store.reverse_paths(terminal_id, config["min_hops"], config["max_hops"])
        for node_ids in raw_paths:
            leaf_id = node_ids[-1]
            product = store.get_product(leaf_id)
            if product is None:
                continue

            keep, reason = passes_niche_filter(product, config)
            if not keep:
                continue

            producers = store.companies_producing(leaf_id)
            filtered = []
            prune_reasons = [f"{product['name']}: {reason}"]
            for c in producers:
                ok, creason = passes_company_filter(c, config)
                if ok:
                    filtered.append(c)
                else:
                    prune_reasons.append(f"{c['name']} 剪枝: {creason}")
            if not filtered:
                continue

            hop_count = len(node_ids) - 1
            hint = max(
                calc_serenity_hint(product, c, hop_count, config) for c in filtered
            )
            path = TracePath(
                path_id=f"path_{terminal_id}_{leaf_id}",
                node_ids=node_ids,
                node_names=[store.get_product(n)["name"] for n in node_ids],
                niche_product_id=leaf_id,
                niche_product_name=product["name"],
                hop_count=hop_count,
                serenity_hint=hint,
                prune_reasons=prune_reasons,
                companies=[
                    {
                        "code": c["code"],
                        "name": c["name"],
                        "market_cap_billion": c.get("market_cap_billion"),
                        "analyst_coverage": c.get("analyst_coverage"),
                        "turnover_percentile": c.get("turnover_percentile"),
                        "serenity_tags": _tags(product, c, config),
                    }
                    for c in filtered
                ],
            )
            # 去重：同一小众环节保留最短路径
            prev = best_by_niche.get(leaf_id)
            if prev is None or hop_count < prev.hop_count:
                best_by_niche[leaf_id] = path

    return sorted(best_by_niche.values(), key=lambda p: -p.serenity_hint)


def _tags(product: dict, company: dict, config: dict) -> list[str]:
    tags = []
    if company.get("market_cap_billion", 1e9) < config["max_market_cap_billion"]:
        tags.append("low_cap")
    if company.get("analyst_coverage", 99) < config["max_analyst_coverage"]:
        tags.append("low_coverage")
    if company.get("turnover_percentile", 1) < config["max_turnover_percentile"]:
        tags.append("low_crowding")
    if product.get("layer") in ("material", "consumable"):
        tags.append("niche_material")
    if product.get("substitution_difficulty") == "high":
        tags.append("rigid_supply")
    return tags
