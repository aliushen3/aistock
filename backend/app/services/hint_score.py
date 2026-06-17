"""瓶颈提示分规则引擎 — 非投资决策分，仅供辅助排序与关注提示。"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class HintScoreResult:
    total: float
    supply_rigidity: float
    tech_barrier: float
    supply_demand_gap: float
    concentration: float
    hint_level: str
    hit_rules: list[dict] = field(default_factory=list)
    provenance_ids: list[str] = field(default_factory=list)
    human_confirmed: bool = False


def _tier_score(value: float, tiers: list[list]) -> float:
    for threshold, score in tiers:
        if value >= threshold:
            return float(score)
    return 0.0


def load_config() -> dict:
    path = Path(__file__).resolve().parents[2] / "config" / "hint_score.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def calc_bottleneck_hint(product: dict) -> HintScoreResult:
    """
    根据产品属性计算瓶颈提示分。
    product 需包含：expansion_cycle_months, cr4_concentration 等字段。
  """
    config = load_config()
    weights = config["weights"]
    thresholds = config["thresholds"]

    expansion = product.get("expansion_cycle_months", 0)
    cr4 = product.get("cr4_concentration", 0)

    supply_rigidity = _tier_score(
        expansion, config["rules"]["expansion_cycle_months"]["tiers"]
    )
    concentration = _tier_score(cr4, config["rules"]["cr4_concentration"]["tiers"])

    # 一期简化：其余分项待产业数据接入后补全
    tech_barrier = float(product.get("tech_barrier_score", 50))
    supply_demand_gap = float(product.get("supply_demand_score", 50))

    total = (
        supply_rigidity * weights["supply_rigidity"]
        + tech_barrier * weights["tech_barrier"]
        + supply_demand_gap * weights["supply_demand_gap"]
        + concentration * weights["concentration"]
    )

    if total >= thresholds["hint_high"]:
        hint_level = "hint_high"
    elif total >= thresholds["hint_medium"]:
        hint_level = "hint_medium"
    elif total >= thresholds["hint_low"]:
        hint_level = "hint_low"
    else:
        hint_level = "none"

    return HintScoreResult(
        total=round(total, 1),
        supply_rigidity=supply_rigidity,
        tech_barrier=tech_barrier,
        supply_demand_gap=supply_demand_gap,
        concentration=concentration,
        hint_level=hint_level,
        hit_rules=[
            {"rule": "expansion_cycle", "value": expansion, "score": supply_rigidity},
            {"rule": "cr4", "value": cr4, "score": concentration},
        ],
        provenance_ids=product.get("provenance_ids", []),
    )
