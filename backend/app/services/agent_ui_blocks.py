"""Agent 响应 → 动态 GUI Block 构建。"""

from __future__ import annotations

import uuid
from typing import Any


def _bid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _metric_cards_block(agent_key: str, payload: dict) -> dict:
    metrics: list[dict] = []
    if payload.get("agent_summary"):
        metrics.append({"key": "summary", "label": "摘要", "value": payload["agent_summary"]})
    for key, label in (
        ("candidate_count", "候选"),
        ("alert_count", "告警"),
        ("bear_case_count", "看空论点"),
        ("high_unrebutted", "高severity待回应"),
        ("path_count", "路径"),
        ("p0_count", "P0"),
        ("scanned_products", "扫描产品"),
    ):
        val = payload.get(key)
        if isinstance(val, int):
            metrics.append({"key": key, "label": label, "value": str(val)})
    if isinstance(payload.get("steps_completed"), int):
        # steps_requested: orchestrator 给列表，data_source_pipeline 给 int，两者都要兼容
        requested = payload.get("steps_requested")
        total = requested if isinstance(requested, int) else len(requested or [])
        metrics.append(
            {
                "key": "steps",
                "label": "流水线",
                "value": f"{payload['steps_completed']}/{total}",
            }
        )
    recs = payload.get("recommendations") or []
    if recs:
        metrics.append({"key": "recs", "label": "推荐", "value": str(len(recs))})
    return {
        "block_id": _bid("metric"),
        "type": "metric_cards",
        "title": "运行摘要",
        "agent_key": agent_key,
        "risk_level": "low",
        "data": {"metrics": metrics, "disclaimer": payload.get("disclaimer")},
        "actions": [],
    }


def _sector_rec_list_block(recs: list[dict]) -> dict:
    return {
        "block_id": _bid("srec"),
        "type": "sector_recommendation_list",
        "title": f"赛道推荐（{len(recs)} 条待采纳）",
        "agent_key": "sector_recommend",
        "risk_level": "medium",
        "data": {"items": recs},
        "actions": [],
    }


def _pipeline_steps_block(results: list[dict], *, agent_key: str = "orchestrator") -> dict:
    return {
        "block_id": _bid("pipe"),
        "type": "pipeline_steps",
        "title": "流水线步骤",
        "agent_key": agent_key,
        "risk_level": "low",
        "data": {"steps": results},
        "actions": [],
    }


def _workflow_progress_block(ws: dict) -> dict:
    return {
        "block_id": _bid("wf"),
        "type": "workflow_progress",
        "title": "工作流进度",
        "agent_key": "orchestrator",
        "risk_level": "low",
        "data": ws,
        "actions": [],
    }


def _bottleneck_rec_block(items: list[dict]) -> dict:
    return {
        "block_id": _bid("bn"),
        "type": "bottleneck_rec_list",
        "title": f"瓶颈提案（{len(items)} 条）",
        "agent_key": "bottleneck_scout",
        "risk_level": "medium",
        "data": {"items": items},
        "actions": [],
    }


def _candidate_table_block(items: list[dict], sector_id: str) -> dict:
    return {
        "block_id": _bid("cand"),
        "type": "candidate_fusion_table",
        "title": f"融合候选（{len(items)} 个）",
        "agent_key": "candidate_fusion",
        "risk_level": "high",
        "data": {"items": items, "sector_id": sector_id},
        "actions": [
            {
                "action_id": "goto_candidates",
                "label": "去候选池确认入池",
                "kind": "primary",
                "api_method": "navigate",
                "api_path": f"/candidates?sector={sector_id}",
            }
        ],
    }


def _knowledge_draft_block(draft_id: str, sector_id: str, extracted: dict | None = None) -> dict:
    return {
        "block_id": _bid("draft"),
        "type": "knowledge_draft_preview",
        "title": "知识草案",
        "agent_key": "knowledge_ingest",
        "risk_level": "medium",
        "data": {
            "draft_id": draft_id,
            "sector_id": sector_id,
            "extracted": extracted or {},
        },
        "actions": [
            {
                "action_id": "goto_knowledge",
                "label": "前往校准确认",
                "kind": "primary",
                "api_method": "navigate",
                "api_path": "/knowledge",
            }
        ],
    }


def _serenity_rec_block(items: list[dict]) -> dict:
    return {
        "block_id": _bid("ser"),
        "type": "serenity_rec_list",
        "title": f"Serenity 路径（{len(items)} 条）",
        "agent_key": "serenity_path",
        "risk_level": "medium",
        "data": {"items": items},
        "actions": [],
    }


def _report_draft_summary_block(report: dict, report_id: str) -> dict:
    return {
        "block_id": _bid("report"),
        "type": "report_draft_summary",
        "title": f"报告草稿 {report_id}",
        "agent_key": "report_graphrag",
        "risk_level": "medium",
        "data": {"report_id": report_id, "report": report},
        "actions": [
            {
                "action_id": "goto_report",
                "label": "前往审核发布",
                "kind": "primary",
                "api_method": "navigate",
                "api_path": "/report",
            }
        ],
    }


def _bear_case_list_block(items: list[dict], sector_id: str) -> dict:
    return {
        "block_id": _bid("bear"),
        "type": "bear_case_list",
        "title": f"看空论点（{len(items)} 条）",
        "agent_key": "bear_case",
        "risk_level": "high",
        "data": {"items": items, "sector_id": sector_id},
        "actions": [],
    }


def _alert_feed_block(
    items: list[dict],
    *,
    title: str = "待办与告警",
    agent_key: str | None = "monitor_watch",
    resume_steps: list[str] | None = None,
) -> dict:
    data: dict[str, Any] = {"items": items}
    if resume_steps:
        data["resume_steps"] = resume_steps
    actions: list[dict] = []
    if resume_steps:
        actions.append(
            {
                "action_id": "resume_orchestrator",
                "label": f"从断点继续（{len(resume_steps)} 步）",
                "kind": "primary",
                "ontology_action": "ResumeOrchestrator",
            }
        )
    return {
        "block_id": _bid("alert"),
        "type": "alert_feed",
        "title": title,
        "agent_key": agent_key,
        "risk_level": "low",
        "data": data,
        "actions": actions,
    }


def build_ui_blocks(agent_key: str, payload: dict) -> list[dict]:
    blocks: list[dict] = [_metric_cards_block(agent_key, payload)]

    if agent_key == "sector_recommend":
        recs = payload.get("recommendations") or []
        if recs:
            blocks.append(_sector_rec_list_block(recs))

    elif agent_key == "orchestrator":
        results = payload.get("results") or []
        if results:
            blocks.append(_pipeline_steps_block(results))
            for step in results:
                step_name = step.get("step") or step.get("agent_key")
                output = step.get("output") or {}
                if step_name and output and step.get("status") == "ok":
                    sub = build_ui_blocks(str(step_name), output)
                    for b in sub:
                        if b["type"] != "metric_cards":
                            blocks.append(b)
        sector_id = payload.get("sector_id")
        if sector_id:
            try:
                from app.services.workflow_progress import get_sector_workflow_status

                blocks.append(_workflow_progress_block(get_sector_workflow_status(sector_id)))
            except ValueError:
                pass

    elif agent_key == "bottleneck_scout":
        items = payload.get("recommendations") or payload.get("saved") or []
        if items:
            blocks.append(_bottleneck_rec_block(items))

    elif agent_key == "candidate_fusion":
        items = payload.get("candidates") or payload.get("items") or payload.get("pool") or []
        sid = payload.get("sector_id", "")
        if items:
            blocks.append(_candidate_table_block(items, sid))

    elif agent_key == "knowledge_ingest":
        draft_id = payload.get("draft_id")
        sector_id = payload.get("sector_id", "")
        if draft_id:
            blocks.append(
                _knowledge_draft_block(draft_id, sector_id, payload.get("extracted"))
            )

    elif agent_key == "serenity_path":
        items = payload.get("recommendations") or []
        if items:
            blocks.append(_serenity_rec_block(items))

    elif agent_key == "report_graphrag":
        report = payload.get("report") or {}
        report_id = payload.get("report_id") or report.get("report_id")
        if report_id:
            blocks.append(_report_draft_summary_block(report, report_id))

    elif agent_key == "bear_case":
        items = payload.get("bear_cases") or []
        sid = payload.get("sector_id", "")
        if items:
            blocks.append(_bear_case_list_block(items, sid))

    elif agent_key == "monitor_watch":
        alerts = list(payload.get("alerts") or [])
        global_alerts = payload.get("global_alerts") or []
        for ga in global_alerts:
            alerts.append({**ga, "scope": "global"})
        if alerts:
            blocks.append(_alert_feed_block(alerts, title=f"监控告警（{len(alerts)} 条）"))

    elif agent_key == "data_source_pipeline":
        results = payload.get("results") or []
        if results:
            blocks.append(_pipeline_steps_block(results, agent_key="data_source_pipeline"))

    return blocks


def build_pending_todos_block(
    todos: list[dict],
    alerts: list[dict] | None = None,
    *,
    resume_steps: list[str] | None = None,
) -> dict | None:
    items: list[dict] = []
    for t in todos:
        items.append({**t, "kind": "todo"})
    for a in alerts or []:
        items.append({**a, "kind": "alert"})
    if not items:
        return None
    title = f"待处理（{len(todos)} 项待办" + (f"，{len(alerts or [])} 条告警" if alerts else "") + "）"
    return _alert_feed_block(items, title=title, agent_key=None, resume_steps=resume_steps)


def attach_ui_blocks(agent_key: str, payload: dict, *, operator: str = "analyst") -> dict:
    from app.services.agent_block_permissions import annotate_block_permissions, filter_ui_blocks

    out = dict(payload)
    raw_blocks = build_ui_blocks(agent_key, payload)
    annotated = [annotate_block_permissions(b) for b in raw_blocks]
    out["ui_blocks"] = filter_ui_blocks(annotated, operator)
    return out
