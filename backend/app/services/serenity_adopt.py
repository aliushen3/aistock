"""Serenity 提案采纳 — 触发 ConfirmSerenityNiche。"""

from __future__ import annotations

from app.ontology.action_executor import ActionError, action_executor
from app.services.serenity_recommendations import get_recommendation, update_status


def confirm_recommendation(rec_id: str, operator: str = "analyst", reason: str | None = None) -> dict:
    rec = get_recommendation(rec_id)
    if rec is None:
        raise ValueError(f"提案不存在: {rec_id}")
    if rec["status"] != "proposed":
        raise ValueError(f"提案状态不可确认: {rec['status']}")

    rationale = reason or rec.get("rationale") or f"采纳 Serenity 提案 {rec_id}"
    try:
        result = action_executor.execute_with_params(
            action_type="ConfirmSerenityNiche",
            target_type="Product",
            target_id=rec["niche_product_id"],
            params={"reason": rationale},
            operator=operator,
        )
    except ActionError as e:
        raise ValueError(e.message) from e

    updated = update_status(rec_id, "confirmed")
    return {
        "rec_id": rec_id,
        "product_id": rec["niche_product_id"],
        "status": "confirmed",
        "action_result": {
            "action_type": result.action_type,
            "message": result.message,
        },
        "recommendation": updated,
    }


def dismiss_recommendation(rec_id: str, operator: str = "analyst") -> dict:
    rec = get_recommendation(rec_id)
    if rec is None:
        raise ValueError(f"提案不存在: {rec_id}")
    updated = update_status(rec_id, "dismissed")
    return {"rec_id": rec_id, "status": "dismissed", "operator": operator, "recommendation": updated}
