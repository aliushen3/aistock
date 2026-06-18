"""Ontology Action 权限校验（一期简化 RBAC）。"""

from __future__ import annotations

# operator 默认角色映射（二期对接真实用户系统）
OPERATOR_ROLES: dict[str, list[str]] = {
    "analyst": ["researcher"],
    "fund_manager": ["fund_manager", "researcher"],
    "risk": ["risk", "researcher"],
    "admin": ["researcher", "fund_manager", "risk", "knowledge_admin"],
}


def resolve_roles(operator: str) -> list[str]:
    return OPERATOR_ROLES.get(operator, ["researcher"])


def check_permission(operator: str, allowed: list[str]) -> bool:
    if not allowed:
        return True
    roles = set(resolve_roles(operator))
    return bool(roles & set(allowed))
