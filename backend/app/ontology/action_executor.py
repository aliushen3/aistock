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
    pending_id: str | None = None
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
        if target_type == "BearCase":
            from app.services import bearcase_store

            return bearcase_store.get_bear_case(target_id)
        return None

    def _check_preconditions(self, preconditions: list[str], obj: dict) -> None:
        for expr in preconditions:
            if expr.startswith("validation:"):
                self._run_validation(expr.split(":", 1)[1].strip(), obj)
                continue
            if "==" in expr:
                left, right = [x.strip() for x in expr.split("==", 1)]
                val = obj.get(left)
                if right in ("true", "false"):
                    expected = right == "true"
                    if bool(val) != expected:
                        raise ActionError(
                            f"前置条件不满足: {expr}（当前 {left}={val}）",
                            "precondition_failed",
                        )
                elif val != right:
                    raise ActionError(
                        f"前置条件不满足: {expr}（当前 {left}={val}）",
                        "precondition_failed",
                    )

    def _run_validation(self, name: str, obj: dict) -> None:
        """命名校验（硬闸门）。三道闸闸三：高severity空头未回应阻断入池。"""
        if name == "bear_rebutted":
            if (obj or {}).get("bear_status") == "unrebutted_high":
                raise ActionError(
                    "存在未回应的高severity空头论点（BearCase），须先执行 RebutBearCase 方可入池",
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
        if action_type == "CalibrateChain":
            return self._execute_calibrate_chain(params, operator)

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

        dual = spec.get("requires_dual_review", False)
        pending_id = None
        if dual:
            from app.services import dual_review

            existing = dual_review.find_pending(action_type, target_type, target_id)
            if existing is None:
                row = dual_review.create_pending(
                    action_type, target_type, target_id, params, operator
                )
                audit_entry = audit_log.record(
                    action=f"ontology.{action_type}.pending",
                    operator=operator,
                    target=f"{target_type}:{target_id}",
                    detail={"params": params, "pending_id": row["pending_id"]},
                )
                return ActionResult(
                    action_type=action_type,
                    target_type=target_type,
                    target_id=target_id,
                    operator=operator,
                    status="pending_review",
                    audit_id=audit_entry.id if audit_entry else None,
                    requires_dual_review=True,
                    pending_id=row["pending_id"],
                    message=f"Action {action_type} 已提交，待第二人复核（pending_id={row['pending_id']}）",
                )
            if existing["first_operator"] == operator:
                raise ActionError("双人复核须由不同操作者执行", "dual_review_same_operator")
            dual_review.approve_pending(existing["pending_id"], operator)
            pending_id = existing["pending_id"]

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
                    value = effect["set"]["value"]
                    if isinstance(value, str) and value.startswith("param:"):
                        value = params.get(value.split(":", 1)[1])
                    object_store.set_object_property(target_type, target_id, prop, value)

        elif target_type == "BearCase":
            from app.services import bearcase_store

            for effect in spec.get("effects", []):
                if "set" in effect and effect["set"]["property"] == "rebuttal_status":
                    bearcase_store.set_rebuttal(target_id, params.get("rebuttal", ""), operator)
                    break

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
        side_context = {
            "subject_type": target_type,
            "subject_id": target_id,
            "operator": operator,
            "reason": params.get("reason", ""),
            "evidence_refs": (obj or {}).get("provenance_ids", []),
            "action_type": action_type,
        }
        for effect in effects_applied:
            if "set" in effect:
                _val = effect["set"]["value"]
                if isinstance(_val, str) and _val.startswith("param:"):
                    _val = params.get(_val.split(":", 1)[1])
                side_context["predicate"] = effect["set"]["property"]
                side_context["object_value"] = str(_val)
                break
        self._run_side_effects(spec.get("side_effects", []), side_context)

        audit_entry = None
        if "audit_log" in spec.get("side_effects", []):
            audit_entry = audit_log.record(
                action=f"ontology.{action_type}",
                operator=operator,
                target=f"{target_type}:{target_id}",
                detail={"params": params, "effects": effects_applied},
            )

        dual_flag = spec.get("requires_dual_review", False)
        msg = f"Action {action_type} 已执行"
        if dual_flag:
            msg += f"（双人复核已通过，pending_id={pending_id}）" if pending_id else "（待双人复核）"
        return ActionResult(
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            operator=operator,
            effects_applied=effects_applied,
            audit_id=audit_entry.id if audit_entry else None,
            requires_dual_review=dual_flag,
            pending_id=pending_id,
            message=msg,
        )

    def _run_side_effects(self, side_effects: list[str], context: dict | None = None) -> None:
        for effect in side_effects:
            if effect == "sync_neo4j":
                from app.ontology.graph_projector import project_graph

                project_graph()
            elif effect == "invalidate_function":
                from app.services.graph_store import invalidate_store_cache

                invalidate_store_cache()
            elif effect == "write_knowledge_assertion" and context:
                from app.ontology import pg_store

                pg_store.save_knowledge_assertion(
                    subject_type=context.get("subject_type", ""),
                    subject_id=context.get("subject_id", ""),
                    predicate=context.get("predicate", ""),
                    object_value=str(context.get("object_value", "")),
                    operator=context.get("operator", "analyst"),
                    reason=context.get("reason", ""),
                    evidence_refs=context.get("evidence_refs", []),
                )
            elif effect == "record_hint_outcome" and context:
                from app.services import hint_calibration

                hint_calibration.record_bottleneck_outcome(
                    product_id=context.get("subject_id", ""),
                    action_type=context.get("action_type", ""),
                    operator=context.get("operator", "analyst"),
                    reason=context.get("reason", ""),
                )

    def _execute_calibrate_chain(self, params: dict[str, Any], operator: str) -> ActionResult:
        spec = ontology_registry.get_action_type("CalibrateChain")
        if spec is None:
            raise ActionError("未知 Action Type: CalibrateChain", "unknown_action")
        if not check_permission(operator, spec.get("permissions", [])):
            raise ActionError(f"操作者 {operator} 无权执行 CalibrateChain", "permission_denied")
        self._validate_params(spec.get("parameters", []), params)

        operation = params.get("operation")
        source_id = params.get("source_id")
        target_id = params.get("target_id")
        if operation not in ("add", "remove", "modify"):
            raise ActionError("operation 须为 add / remove / modify", "invalid_params")

        from app.ontology import pg_store
        from app.services.graph_store import get_store, invalidate_store_cache

        store = get_store()
        if store.get_product(source_id) is None or store.get_product(target_id) is None:
            raise ActionError("source_id 或 target_id 产品不存在", "not_found")

        changed = False
        if operation == "add":
            changed = (
                pg_store.add_upstream_link(source_id, target_id)
                if pg_store.is_db_enabled()
                else store.add_upstream_link(source_id, target_id)
            )
        elif operation == "remove":
            changed = (
                pg_store.remove_upstream_link(source_id, target_id)
                if pg_store.is_db_enabled()
                else store.remove_upstream_link(source_id, target_id)
            )
        elif operation == "modify":
            old_target = params.get("old_target_id")
            if not old_target:
                raise ActionError("modify 操作需 old_target_id", "invalid_params")
            if pg_store.is_db_enabled():
                pg_store.remove_upstream_link(source_id, old_target)
                changed = pg_store.add_upstream_link(source_id, target_id)
            else:
                store.remove_upstream_link(source_id, old_target)
                changed = store.add_upstream_link(source_id, target_id)

        if not changed and operation != "modify":
            raise ActionError("链路未变更（可能已存在或不存在）", "no_change")

        invalidate_store_cache()
        link_id = f"{source_id}:{target_id}"
        audit_entry = audit_log.record(
            action="ontology.CalibrateChain",
            operator=operator,
            target=f"Link.upstream_of:{link_id}",
            detail={"params": params, "operation": operation},
        )
        return ActionResult(
            action_type="CalibrateChain",
            target_type="Link.upstream_of",
            target_id=link_id,
            operator=operator,
            effects_applied=[{"operation": operation, "source_id": source_id, "target_id": target_id}],
            audit_id=audit_entry.id,
            message=f"产业链关系已{operation}",
        )


action_executor = ActionExecutor()
