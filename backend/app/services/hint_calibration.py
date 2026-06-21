"""提示分校准闭环 — 人工裁决 outcome 记录与权重版本回流（DESIGN §6.1 / §11.1）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import OntHintOutcome
from app.db.session import SessionLocal
from app.services.hint_score import calc_bottleneck_hint, load_config
from app.ontology import pg_store
from app.ontology.object_store import get_product

_memory_outcomes: list[dict] = []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_bottleneck_outcome(
    product_id: str,
    action_type: str,
    operator: str,
    reason: str = "",
) -> dict:
    """ConfirmBottleneck / RejectBottleneck / ConfirmBottleneckEasing 后记录 outcome。"""
    product = get_product(product_id)
    if product is None:
        raise ValueError(f"产品不存在: {product_id}")

    config = load_config()
    result = calc_bottleneck_hint(product)
    outcome_id = f"out_{uuid.uuid4().hex[:12]}"
    row = {
        "outcome_id": outcome_id,
        "product_id": product_id,
        "sector_id": product.get("sector_id"),
        "hint_score": result.total,
        "hint_level": result.hint_level,
        "weight_version": config.get("weight_version", config.get("version", "unknown")),
        "weights_snapshot": dict(config.get("weights", {})),
        "action_type": action_type,
        "verdict": _verdict_from_action(action_type),
        "outcome_status": "pending",
        "operator": operator,
        "reason": reason,
        "recorded_at": _now_iso(),
        "resolved_at": None,
    }
    _memory_outcomes.append(row)

    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            db.add(
                OntHintOutcome(
                    outcome_id=outcome_id,
                    product_id=product_id,
                    sector_id=product.get("sector_id"),
                    hint_score=result.total,
                    hint_level=result.hint_level,
                    weight_version=row["weight_version"],
                    weights_snapshot=row["weights_snapshot"],
                    action_type=action_type,
                    verdict=row["verdict"],
                    outcome_status="pending",
                    operator=operator,
                    reason=reason,
                )
            )
            db.commit()
        finally:
            db.close()
    return row


def _verdict_from_action(action_type: str) -> str:
    mapping = {
        "ConfirmBottleneck": "confirmed",
        "RejectBottleneck": "rejected",
        "ConfirmBottleneckEasing": "easing",
    }
    return mapping.get(action_type, action_type.lower())


def list_outcomes(
    sector_id: str | None = None,
    outcome_status: str | None = None,
    limit: int = 100,
) -> list[dict]:
    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            q = select(OntHintOutcome)
            if sector_id:
                q = q.where(OntHintOutcome.sector_id == sector_id)
            if outcome_status:
                q = q.where(OntHintOutcome.outcome_status == outcome_status)
            rows = db.scalars(q.order_by(OntHintOutcome.recorded_at.desc()).limit(limit)).all()
            return [_row_to_dict(r) for r in rows]
        finally:
            db.close()

    items = list(_memory_outcomes)
    if sector_id:
        items = [x for x in items if x.get("sector_id") == sector_id]
    if outcome_status:
        items = [x for x in items if x.get("outcome_status") == outcome_status]
    return items[:limit]


def _row_to_dict(row: OntHintOutcome) -> dict:
    return {
        "outcome_id": row.outcome_id,
        "product_id": row.product_id,
        "sector_id": row.sector_id,
        "hint_score": row.hint_score,
        "hint_level": row.hint_level,
        "weight_version": row.weight_version,
        "weights_snapshot": row.weights_snapshot,
        "action_type": row.action_type,
        "verdict": row.verdict,
        "outcome_status": row.outcome_status,
        "operator": row.operator,
        "reason": row.reason,
        "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }


def resolve_outcome(outcome_id: str, outcome_status: str, operator: str = "analyst") -> dict | None:
    if outcome_status not in ("fulfilled", "false_positive", "inconclusive"):
        raise ValueError("outcome_status 须为 fulfilled / false_positive / inconclusive")

    if pg_store.is_db_enabled():
        db = SessionLocal()
        try:
            row = db.get(OntHintOutcome, outcome_id)
            if row is None:
                return None
            row.outcome_status = outcome_status
            row.resolved_at = datetime.now(timezone.utc)
            db.commit()
            return _row_to_dict(row)
        finally:
            db.close()

    for row in _memory_outcomes:
        if row["outcome_id"] == outcome_id:
            row["outcome_status"] = outcome_status
            row["resolved_at"] = _now_iso()
            return row
    return None


def calibration_summary() -> dict[str, Any]:
    """各分档命中率与校准状态。"""
    config = load_config()
    min_samples = int(config.get("calibration", {}).get("min_samples", 10))
    outcomes = list_outcomes(limit=500)
    resolved = [o for o in outcomes if o.get("outcome_status") in ("fulfilled", "false_positive")]
    confirmed = [o for o in outcomes if o.get("verdict") == "confirmed"]
    fulfilled_confirmed = [
        o for o in confirmed if o.get("outcome_status") == "fulfilled"
    ]

    tier_stats: dict[str, dict] = {}
    for level in ("hint_high", "hint_medium", "hint_low"):
        tier_rows = [o for o in confirmed if o.get("hint_level") == level]
        tier_resolved = [
            o for o in tier_rows if o.get("outcome_status") in ("fulfilled", "false_positive")
        ]
        tier_fulfilled = [o for o in tier_resolved if o.get("outcome_status") == "fulfilled"]
        tier_stats[level] = {
            "confirmed_count": len(tier_rows),
            "resolved_count": len(tier_resolved),
            "hit_rate": round(len(tier_fulfilled) / len(tier_resolved), 3) if tier_resolved else None,
        }

    hit_rate = round(len(fulfilled_confirmed) / len(resolved), 3) if resolved else None
    calibrated = len(confirmed) >= min_samples and hit_rate is not None

    return {
        "weight_version": config.get("weight_version", config.get("version")),
        "weights": config.get("weights", {}),
        "thresholds": config.get("thresholds", {}),
        "min_samples": min_samples,
        "calibrated": calibrated,
        "calibration_note": (
            "权重已基于 outcome 校准"
            if calibrated
            else "权重未校准（初始先验），请谨慎采信提示分"
        ),
        "total_outcomes": len(outcomes),
        "confirmed_count": len(confirmed),
        "resolved_count": len(resolved),
        "overall_hit_rate": hit_rate,
        "tier_stats": tier_stats,
    }


def suggest_weight_adjustments() -> dict[str, Any]:
    """基于 outcome 命中率给出透明权重调整建议（不引入黑盒）。"""
    summary = calibration_summary()
    config = load_config()
    if not summary["calibrated"]:
        return {
            "weight_version": summary["weight_version"],
            "calibrated": False,
            "message": summary["calibration_note"],
            "suggested_weights": dict(config.get("weights", {})),
        }

    weights = dict(config.get("weights", {}))
    hit = summary["overall_hit_rate"] or 0.5
    target = float(config.get("calibration", {}).get("target_hit_rate", 0.6))
    delta = round((hit - target) * 0.05, 4)
    adjusted = {
        k: round(max(0.05, min(0.5, v + delta)), 4) for k, v in weights.items()
    }
    total = sum(adjusted.values())
    normalized = {k: round(v / total, 4) for k, v in adjusted.items()}
    new_version = f"{summary['weight_version']}-adj"

    return {
        "weight_version": summary["weight_version"],
        "proposed_weight_version": new_version,
        "calibrated": True,
        "overall_hit_rate": hit,
        "target_hit_rate": target,
        "current_weights": weights,
        "suggested_weights": normalized,
        "message": "建议权重调整基于确认样本命中率，须人工审核后写入 hint_score.yaml",
    }
