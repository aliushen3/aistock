"""UI Block / Action 权限过滤 — 对齐 Ontology RBAC 与导航 roles。"""

from __future__ import annotations

from typing import Any

from app.ontology.permissions import check_permission, resolve_roles

# block type → 可见角色（空=全员）
BLOCK_REQUIRED_ROLES: dict[str, list[str]] = {
    "metric_cards": [],
    "pipeline_steps": [],
    "workflow_progress": [],
    "alert_feed": [],
    "sector_recommendation_list": ["researcher", "fund_manager", "admin"],
    "sector_pending_confirm_list": ["researcher", "fund_manager", "admin"],
    "sector_settled_list": ["researcher", "fund_manager", "admin"],
    "bottleneck_rec_list": ["researcher", "fund_manager", "admin"],
    "serenity_rec_list": ["researcher", "fund_manager", "admin"],
    "knowledge_draft_preview": ["researcher", "knowledge_admin", "data_admin", "admin"],
    "report_draft_summary": ["researcher", "fund_manager", "admin"],
    "candidate_fusion_table": ["fund_manager", "admin"],
    "bear_case_list": ["researcher", "risk", "fund_manager", "admin"],
}

# action_id → 执行角色
ACTION_REQUIRED_ROLES: dict[str, list[str]] = {
    "goto_candidates": ["fund_manager", "admin"],
    "goto_report": ["researcher", "fund_manager", "admin"],
    "goto_knowledge": ["researcher", "knowledge_admin", "data_admin", "admin"],
    "resume_orchestrator": ["researcher", "fund_manager", "admin"],
}

INTERACTION_REQUIRED_ROLES: dict[str, list[str]] = {
    "adopt_sector": ["fund_manager", "admin"],
    "dismiss_proposal": ["researcher", "fund_manager", "risk", "admin", "data_admin"],
    "confirm_serenity": ["researcher", "fund_manager", "admin"],
    "confirm_sector_beta": ["researcher", "fund_manager", "admin"],
    "rebut_bear": ["fund_manager", "risk", "admin"],
}


def _roles_allowed(operator: str, required: list[str]) -> bool:
    if not required:
        return True
    return check_permission(operator, required)


def annotate_block_permissions(block: dict[str, Any]) -> dict[str, Any]:
    """构建时为 Block 附加 required_roles / 过滤 actions。"""
    btype = block.get("type", "")
    required = block.get("required_roles")
    if required is None:
        required = BLOCK_REQUIRED_ROLES.get(btype, [])
    out = {**block, "required_roles": required}
    actions = []
    for action in block.get("actions") or []:
        aid = action.get("action_id", "")
        action_roles = action.get("required_roles") or ACTION_REQUIRED_ROLES.get(aid, [])
        actions.append({**action, "required_roles": action_roles})
    out["actions"] = actions
    return out


def filter_ui_blocks(blocks: list[dict], operator: str = "analyst") -> list[dict]:
    """按 operator 过滤不可见 Block，并裁剪无权限 Action。"""
    visible: list[dict] = []
    for block in blocks:
        annotated = annotate_block_permissions(block)
        required = annotated.get("required_roles") or []
        if not _roles_allowed(operator, required):
            continue
        filtered_actions = [
            a
            for a in annotated.get("actions") or []
            if _roles_allowed(operator, a.get("required_roles") or [])
        ]
        visible.append({**annotated, "actions": filtered_actions})
    return visible


def get_interaction_permissions(operator: str) -> dict[str, bool]:
    return {k: _roles_allowed(operator, v) for k, v in INTERACTION_REQUIRED_ROLES.items()}


def block_type_visible(operator: str, block_type: str) -> bool:
    return _roles_allowed(operator, BLOCK_REQUIRED_ROLES.get(block_type, []))
