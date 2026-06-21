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
    freshness: str = "unknown"
    weight_version: str = "unknown"
    weight_breakdown: dict = field(default_factory=dict)
    calibrated: bool = False
    calibration_note: str = ""


def _tier_score(value: float, tiers: list[list]) -> float:
    for threshold, score in tiers:
        if value >= threshold:
            return float(score)
    return 0.0


def load_config() -> dict:
    path = Path(__file__).resolve().parents[2] / "config" / "hint_score.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _enum_score(value: str, mapping: dict) -> float:
    return float(mapping.get(value, mapping.get("low", 20)))


def calc_bottleneck_hint(product: dict) -> HintScoreResult:
    """根据产品属性计算瓶颈提示分（DESIGN §2.3 / §7.1）。"""
    config = load_config()
    weights = config["weights"]
    thresholds = config["thresholds"]
    rules = config["rules"]

    expansion = product.get("expansion_cycle_months", 0)
    cr4 = product.get("cr4_concentration", 0)
    certification = product.get("certification_months", 0)

    expansion_score = _tier_score(expansion, rules["expansion_cycle_months"]["tiers"])
    cert_score = _tier_score(certification, rules["certification_months"]["tiers"])
    supply_rigidity = max(expansion_score, cert_score)

    concentration = _tier_score(cr4, rules["cr4_concentration"]["tiers"])

    overseas = _enum_score(
        product.get("overseas_dependence", "low"), rules["overseas_dependence"]
    )
    substitution = _enum_score(
        product.get("substitution_difficulty", "medium"), rules["substitution_difficulty"]
    )
    tech_barrier = max(
        float(product.get("tech_barrier_score", 50)),
        overseas * 0.4 + substitution * 0.6,
    )

    supply_demand_gap = float(product.get("supply_demand_score", 50))
    if product.get("bottleneck_status") in ("bottleneck_hint", "bottleneck_confirmed"):
        supply_demand_gap = max(supply_demand_gap, 70)

    total = (
        supply_rigidity * weights["supply_rigidity"]
        + tech_barrier * weights["tech_barrier"]
        + supply_demand_gap * weights["supply_demand_gap"]
        + concentration * weights["concentration"]
    )

    # 知识保鲜（主线二）：stale 数据轻度降权并标注
    from app.services.freshness import product_freshness

    freshness = product_freshness(product)["freshness"]
    stale_note = None
    if freshness == "stale":
        total *= 0.85
        stale_note = {"rule": "freshness", "value": "stale", "score": 0, "note": "数据过期，降权 15%"}

    if total >= thresholds["hint_high"]:
        hint_level = "hint_high"
    elif total >= thresholds["hint_medium"]:
        hint_level = "hint_medium"
    elif total >= thresholds["hint_low"]:
        hint_level = "hint_low"
    else:
        hint_level = "none"

    hit_rules = [
        {"rule": "expansion_cycle", "value": expansion, "score": expansion_score},
        {"rule": "certification_months", "value": certification, "score": cert_score},
        {"rule": "cr4", "value": cr4, "score": concentration},
        {"rule": "overseas_dependence", "value": product.get("overseas_dependence"), "score": overseas},
        {
            "rule": "substitution_difficulty",
            "value": product.get("substitution_difficulty"),
            "score": substitution,
        },
    ]

    if stale_note:
        hit_rules.append(stale_note)

    weight_version = config.get("weight_version", config.get("version", "unknown"))
    weight_breakdown = {
        "supply_rigidity": round(supply_rigidity * weights["supply_rigidity"], 2),
        "tech_barrier": round(tech_barrier * weights["tech_barrier"], 2),
        "supply_demand_gap": round(supply_demand_gap * weights["supply_demand_gap"], 2),
        "concentration": round(concentration * weights["concentration"], 2),
    }
    min_samples = int(config.get("calibration", {}).get("min_samples", 10))
    try:
        from app.services.hint_calibration import calibration_summary

        cal = calibration_summary()
        calibrated = cal.get("calibrated", False)
        calibration_note = cal.get("calibration_note", "")
    except Exception:
        calibrated = False
        calibration_note = "权重未校准（初始先验），请谨慎采信"

    return HintScoreResult(
        total=round(total, 1),
        supply_rigidity=round(supply_rigidity, 1),
        tech_barrier=round(tech_barrier, 1),
        supply_demand_gap=round(supply_demand_gap, 1),
        concentration=round(concentration, 1),
        hint_level=hint_level,
        hit_rules=hit_rules,
        provenance_ids=product.get("provenance_ids", []),
        human_confirmed=product.get("bottleneck_status") == "bottleneck_confirmed",
        freshness=freshness,
        weight_version=weight_version,
        weight_breakdown=weight_breakdown,
        calibrated=calibrated,
        calibration_note=calibration_note,
    )


def score_card(product: dict) -> dict:
    """完整 Score Card（含 weight_version / weight_breakdown / 校准状态）。"""
    result = calc_bottleneck_hint(product)
    config = load_config()
    return {
        "product_id": product.get("id"),
        "product_name": product.get("name"),
        "hint_score": result.total,
        "hint_level": result.hint_level,
        "weight_version": result.weight_version,
        "weights": config.get("weights", {}),
        "weight_breakdown": result.weight_breakdown,
        "breakdown": {
            "supply_rigidity": result.supply_rigidity,
            "tech_barrier": result.tech_barrier,
            "supply_demand_gap": result.supply_demand_gap,
            "concentration": result.concentration,
        },
        "hit_rules": result.hit_rules,
        "freshness": result.freshness,
        "calibrated": result.calibrated,
        "calibration_note": result.calibration_note,
        "evidence_refs": [{"ref_id": rid} for rid in result.provenance_ids],
        "disclaimer": "本分数为辅助排序提示，不构成投资建议",
    }
