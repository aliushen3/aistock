"""投研流程门控 — 关键节点须人工确认后方可继续。"""

from __future__ import annotations

from app.ontology.object_store import get_sector


class WorkflowGateError(Exception):
    def __init__(self, message: str, code: str = "workflow_gate"):
        super().__init__(message)
        self.message = message
        self.code = code


def is_sector_confirmed(sector_id: str) -> bool:
    sector = get_sector(sector_id)
    if sector is None:
        return False
    return sector.get("status") == "beta_confirmed" and sector.get("human_confirmed", False)


def require_sector_confirmed(sector_id: str) -> None:
    sector = get_sector(sector_id)
    if sector is None:
        raise WorkflowGateError(f"赛道不存在: {sector_id}", "not_found")
    if not is_sector_confirmed(sector_id):
        raise WorkflowGateError(
            f"赛道「{sector['name']}」尚未确认景气（当前 status={sector.get('status')}），"
            "请研究员先执行 ConfirmSectorBeta",
            "sector_not_confirmed",
        )
