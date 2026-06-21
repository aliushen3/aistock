"""多源交叉与卖方去偏 — 来源权重、交叉验证、自反性叙事（DESIGN §5.8）。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_CONFIDENCE_RANK = {"high": 0.9, "medium": 0.7, "low": 0.5}


def load_source_config() -> dict:
    path = Path(__file__).resolve().parents[2] / "config" / "source_weights.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_source_weight(source_type: str) -> float:
    cfg = load_source_config()
    weights = cfg.get("source_weights", {})
    return float(weights.get(source_type, weights.get("default", 0.4)))


def is_hard_source(source_type: str) -> bool:
    cfg = load_source_config()
    return source_type in cfg.get("hard_sources", [])


def compute_confidence(source_type: str, extract_confidence: str | float) -> float:
    if isinstance(extract_confidence, (int, float)):
        extract_score = float(extract_confidence)
    else:
        extract_score = _CONFIDENCE_RANK.get(str(extract_confidence).lower(), 0.5)
    return round(get_source_weight(source_type) * extract_score, 3)


def _normalize_origin(source_ref: str, source_type: str) -> str:
    ref = (source_ref or "").strip().lower()
    if not ref:
        return f"{source_type}:unknown"
    broker_match = re.search(r"(中信|中金|华泰|国泰君安|海通|广发|招商|申万|天风|国盛)", ref)
    if broker_match:
        return f"broker:{broker_match.group(1)}"
    return f"{source_type}:{ref[:48]}"


def detect_reflexive_narrative(provenance: list[dict]) -> bool:
    """多份研报实为同源观点扩散 → reflexive_narrative。"""
    report_origins: list[str] = []
    for item in provenance:
        st = item.get("source_type", "")
        if st in ("research_report", "broker_deep"):
            report_origins.append(_normalize_origin(item.get("source_ref", ""), st))
    if len(report_origins) < 2:
        return False
    unique = set(report_origins)
    return len(unique) == 1


def dedupe_provenance(provenance: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in provenance:
        key = (
            item.get("source_type", ""),
            _normalize_origin(item.get("source_ref", ""), item.get("source_type", "")),
            item.get("relation_key", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def validate_relation_promotion(
    relation: dict,
    draft_source_type: str,
    draft_source_ref: str,
    existing_provenance: list[dict] | None = None,
) -> dict[str, Any]:
    """单一研报不得单独 confirm；硬源或 ≥2 独立来源。"""
    cfg = load_source_config()
    min_sources = int(cfg.get("min_independent_sources", 2))

    rel_key = f"{relation.get('source_id')}:{relation.get('target_id')}"
    provenance = list(existing_provenance or [])
    provenance.append(
        {
            "source_type": draft_source_type,
            "source_ref": draft_source_ref,
            "relation_key": rel_key,
            "confidence": compute_confidence(
                draft_source_type, relation.get("confidence", "medium")
            ),
        }
    )
    provenance = dedupe_provenance(provenance)

    hard_hits = [p for p in provenance if is_hard_source(p.get("source_type", ""))]
    report_only = all(
        p.get("source_type") in ("research_report", "broker_deep", "llm_extract", "rule_extract")
        for p in provenance
    )
    reflexive = detect_reflexive_narrative(provenance) if report_only else False

    independent_count = len(
        {
            _normalize_origin(p.get("source_ref", ""), p.get("source_type", ""))
            for p in provenance
        }
    )

    can_confirm = len(hard_hits) >= 1 or independent_count >= min_sources
    if reflexive:
        can_confirm = False

    return {
        "can_confirm": can_confirm,
        "independent_source_count": independent_count,
        "hard_source_count": len(hard_hits),
        "report_only": report_only,
        "reflexive_narrative": reflexive,
        "provenance": provenance,
        "validation_note": _validation_note(can_confirm, reflexive, report_only, min_sources),
    }


def _validation_note(
    can_confirm: bool,
    reflexive: bool,
    report_only: bool,
    min_sources: int,
) -> str:
    if reflexive:
        return "检测到自反性叙事（同源研报扩散），须硬源交叉验证"
    if can_confirm:
        return "多源交叉验证通过"
    if report_only:
        return f"仅卖方研报来源，需 ≥{min_sources} 独立来源或 1 个硬源"
    return f"来源不足，需 ≥{min_sources} 独立来源或 1 个硬源"


def enrich_relation(
    relation: dict,
    source_type: str,
    source_ref: str,
) -> dict:
    enriched = dict(relation)
    enriched["source_type"] = source_type
    enriched["source_ref"] = source_ref
    enriched["source_weight"] = get_source_weight(source_type)
    enriched["computed_confidence"] = compute_confidence(
        source_type, relation.get("confidence", "medium")
    )
    enriched["requires_review"] = enriched["computed_confidence"] < 0.5 or source_type in (
        "llm_extract",
        "rule_extract",
    )
    return enriched
