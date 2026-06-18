"""Ontology Action 执行引擎 — 人工投研操作统一入口。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ontology import object_store
from app.ontology.permissions import check_permission
from app.ontology.registry import ontology_registry
from app.services.audit import audit_log


class ActionError(Exception):
    def __init__(self, message: str, code: str = "action_error"):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ActionResult:
    action_type: str
    target_type: str
    target_id: str
    operator: str
    status: str = "success"
    effects_applied: list[dict] = field(default_factory=list)
    audit_id: int | None = None
    requires_dual_review: bool = False
    message: str = ""


class ActionExecutor:
    def execute(
        self,
        action_type: str,
        target_type: str,
        target_id: str,
        params: dict[str, Any],
        operator: str = "analyst",
    ) -> ActionResult:
        spec = ontology_registry.get_action_type(action_type)
        if spec is None:
            raise ActionError(f"未知 Action Type: {action_type}", "unknown_action")

        if spec.get("target") != target_type and not (
            action_type == "CalibrateChain" and target_type.startswith("Link")
        ):
            raise ActionError(
                f"Action {action_type} 的目标类型应为 {spec.get('target')}，收到 {target_type}",
                "target_mismatch",
            )

        allowed = spec.get("permissions", [])
        if not check_permission(operator, allowed):
            raise ActionError(f"操作者 {operator} 无权执行 {action_type}", "permission_denied")

        self._validate_params(spec.get("parameters", []), params)

        obj = self._load_target(target_type, target_id)
        if obj is None:
            raise ActionError(f"对象不存在: {target_type}/{target_id}", "not_found")

        self._check_preconditions(spec.get("preconditions", []), obj)

        effects_applied = self._apply_effects(spec.get("effects", []), target_type, target_id, obj)

        audit_entry = None
        if "audit_log" in spec.get("side_effects", []):
            audit_entry = audit_log.record(
                action=f"ontology.{action_type}",
                operator=operator,
                target=f"{target_type}:{target_id}",
                detail={"params": params, "effects": effects_applied},
            )

        dual = spec.get("requires_dual_review", False)
        msg = f"Action {action_type} 已执行"
        if dual:
            msg += "（已记录，待双人复核生效）"

        return ActionResult(
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            operator=operator,
            effects_applied=effects_applied,
            audit_id=audit_entry.id if audit_entry else None,
            requires_dual_review=dual,
            message=msg,
        )

    def execute_batch_pool(
        self,
        action_type: str,
        sector_id: str,
        mode: str,
        stock_codes: list[str],
        reason: str,
        operator: str = "analyst",
    ) -> list[ActionResult]:
        """批量对候选池条目执行 ApprovePoolEntry / RejectPoolEntry。"""
        results = []
        for code in stock_codes:
            entry_id = object_store.make_candidate_entry_id(sector_id, mode, code)
            results.append(
                self.execute(
                    action_type=action_type,
                    target_type="CandidatePoolEntry",
                    target_id=entry_id,
                    params={"reason": reason},
                    operator=operator,
                )
            )
        return results

    def _validate_params(self, param_specs: list[dict], params: dict) -> None:
        for p in param_specs:
            name = p["name"]
            if p.get("required") and name not in params:
                raise ActionError(f"缺少必填参数: {name}", "invalid_params")
            if name in params and p.get("type") == "string":
                val = params[name]
                min_len = p.get("min_length")
                if min_len and len(str(val).strip()) < min_len:
                    raise ActionError(f"参数 {name} 至少 {min_len} 个字符", "invalid_params")

    def _load_target(self, target_type: str, target_id: str) -> dict | None:
        if target_type == "Sector":
            return object_store.get_sector(target_id)
        if target_type == "Product":
            return object_store.get_product(target_id)
        if target_type == "CandidatePoolEntry":
            return object_store.get_candidate_entry(target_id)
        if target_type == "ResearchReport":
            return object_store.get_research_report(target_id)
        return None

    def _check_preconditions(self, preconditions: list[str], obj: dict) -> None:
        for expr in preconditions:
            if "==" in expr:
                left, right = [x.strip() for x in expr.split("==", 1)]
                if obj.get(left) != right:
                    raise ActionError(
                        f"前置条件不满足: {expr}（当前 {left}={obj.get(left)}）",
                        "precondition_failed",
                    )

    def _apply_effects(
        self, effects: list[dict], target_type: str, target_id: str, obj: dict
    ) -> list[dict]:
        applied = []
        for effect in effects:
            if "set" in effect:
                prop = effect["set"]["property"]
                value = effect["set"]["value"]
                if target_type == "CandidatePoolEntry":
                    sector_id, mode, stock_code = object_store.parse_candidate_entry_id(target_id)
                    reason = obj.get("_pending_reason", "ontology action")
                    operator = obj.get("_pending_operator", "analyst")
                    # reason/operator 由 execute 传入 params，在专用 handler 处理
                    applied.append({"set": prop, "value": value})
                elif target_type in ("Sector", "Product"):
                    object_store.set_object_property(target_type, target_id, prop, value)
                    applied.append({"set": prop, "value": value})
        return applied

    def execute_with_params(
        self,
        action_type: str,
        target_type: str,
        target_id: str,
        params: dict[str, Any],
        operator: str = "analyst",
    ) -> ActionResult:
        """完整执行含 CandidatePoolEntry 状态写回。"""
        spec = ontology_registry.get_action_type(action_type)
        if spec is None:
            raise ActionError(f"未知 Action Type: {action_type}", "unknown_action")

        if not check_permission(operator, spec.get("permissions", [])):
            raise ActionError(f"操作者 {operator} 无权执行 {action_type}", "permission_denied")

        self._validate_params(spec.get("parameters", []), params)

        obj = self._load_target(target_type, target_id)
        if obj is None:
            raise ActionError(f"对象不存在: {target_type}/{target_id}", "not_found")

        self._check_preconditions(spec.get("preconditions", []), obj)

        if target_type == "CandidatePoolEntry":
            for effect in spec.get("effects", []):
                if "set" in effect and effect["set"]["property"] == "status":
                    new_status = effect["set"]["value"]
                    object_store.update_candidate_entry(
                        target_id, new_status, params.get("reason", ""), operator
                    )
                    break

        elif target_type in ("Sector", "Product"):
            for effect in spec.get("effects", []):
                if "set" in effect:
                    prop = effect["set"]["property"]
                    object_store.set_object_property(target_type, target_id, prop, effect["set"]["value"])

        elif target_type == "ResearchReport":
            for effect in spec.get("effects", []):
                if "set" in effect and effect["set"]["property"] == "status":
                    object_store.update_research_report_status(
                        target_id,
                        effect["set"]["value"],
                        review={"comments": params.get("comments", ""), "operator": operator},
                    )
                    break

        effects_applied = spec.get("effects", [])
        self._run_side_effects(spec.get("side_effects", []))

        audit_entry = None
        if "audit_log" in spec.get("side_effects", []):
            audit_entry = audit_log.record(
                action=f"ontology.{action_type}",
                operator=operator,
                target=f"{target_type}:{target_id}",
                detail={"params": params, "effects": effects_applied},
            )

        dual = spec.get("requires_dual_review", False)
        return ActionResult(
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            operator=operator,
            effects_applied=effects_applied,
            audit_id=audit_entry.id if audit_entry else None,
            requires_dual_review=dual,
            message=f"Action {action_type} 已执行" + ("（待双人复核）" if dual else ""),
        )

    def _run_side_effects(self, side_effects: list[str]) -> None:
        for effect in side_effects:
            if effect == "sync_neo4j":
                from app.ontology.graph_projector import project_graph

                project_graph()
            elif effect == "invalidate_function":
                from app.services.graph_store import invalidate_store_cache

                invalidate_store_cache()


action_executor = ActionExecutor()
