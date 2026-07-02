"""Agent 运行 SSE 事件流。"""

from __future__ import annotations

import json
import uuid
from typing import Any, Generator

from app.agents.bearcase_agent import run_bearcase_agent
from app.agents.bottleneck_scout_agent import run_bottleneck_scout_agent
from app.agents.candidate_fusion_agent import run_candidate_fusion_agent
from app.agents.knowledge_ingest_agent import run_knowledge_ingest_agent
from app.agents.monitor_watch_agent import run_monitor_watch_agent
from app.agents.orchestrator import (
    DEFAULT_STEPS,
    GATED_STEPS,
    STEP_HANDLERS,
    run_invest_research_orchestrator,
)
from app.agents.registry import get_agent_spec
from app.agents.report_graphrag_agent import run_report_graphrag_agent
from app.agents.sector_recommend_agent import run_sector_recommend_agent
from app.agents.serenity_path_agent import run_serenity_path_agent
from app.services.agent_ui_blocks import attach_ui_blocks, build_ui_blocks
from app.services.agent_block_permissions import annotate_block_permissions, filter_ui_blocks
from app.services.llm_client import iterate_text_chunks
from app.services.workflow import WorkflowGateError, is_sector_confirmed


def sse_encode(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _run_agent_sync(agent_key: str, params: dict[str, Any]) -> dict[str, Any]:
    if agent_key == "sector_recommend":
        return run_sector_recommend_agent(
            focus=params.get("focus"),
            query=params.get("query"),
            max_recommendations=int(params.get("max_recommendations") or 5),
            force_cold_start=bool(params.get("force_cold_start")),
        )
    if agent_key == "orchestrator":
        steps = params.get("steps")
        if params.get("resume") and not steps:
            from app.services.workflow_progress import get_resume_steps

            sector_id = params.get("sector_id")
            steps = get_resume_steps(sector_id, mode=params.get("mode", "fusion")) if sector_id else None
            if not steps:
                steps = ["monitor_watch"]
        return run_invest_research_orchestrator(
            sector_id=params.get("sector_id", "sector_ai_compute"),
            focus=params.get("focus"),
            query=params.get("query"),
            content=params.get("content"),
            source_ref=params.get("source_ref", "orchestrator"),
            mode=params.get("mode", "fusion"),
            steps=steps,
            stop_on_gate=bool(params.get("stop_on_gate")),
        )
    if agent_key == "bottleneck_scout":
        return run_bottleneck_scout_agent(sector_id=params["sector_id"])
    if agent_key == "serenity_path":
        return run_serenity_path_agent(sector_id=params["sector_id"])
    if agent_key == "candidate_fusion":
        return run_candidate_fusion_agent(sector_id=params["sector_id"], mode=params.get("mode", "fusion"))
    if agent_key == "report_graphrag":
        return run_report_graphrag_agent(sector_id=params["sector_id"], mode=params.get("mode", "fusion"))
    if agent_key == "monitor_watch":
        return run_monitor_watch_agent(sector_id=params.get("sector_id"), mode=params.get("mode", "fusion"))
    if agent_key == "knowledge_ingest":
        return run_knowledge_ingest_agent(
            sector_id=params["sector_id"],
            source_ref=params.get("source_ref", "LUI对话"),
            content=params["content"],
        )
    if agent_key == "bear_case":
        return run_bearcase_agent(sector_id=params["sector_id"], mode=params.get("mode", "fusion"))
    raise ValueError(f"未知 Agent: {agent_key}")


def _yield_block(block: dict[str, Any], operator: str) -> dict[str, Any] | None:
    annotated = annotate_block_permissions(block)
    filtered = filter_ui_blocks([annotated], operator)
    return filtered[0] if filtered else None


def iter_agent_run_events(
    agent_key: str, params: dict[str, Any], *, operator: str = "analyst"
) -> Generator[dict[str, Any], None, None]:
    yield {"event": "agent_start", "data": {"agent_key": agent_key}}

    if agent_key == "orchestrator":
        step_names = params.get("steps") or DEFAULT_STEPS
        if params.get("resume") and not params.get("steps"):
            from app.services.workflow_progress import get_resume_steps

            sector_id = params.get("sector_id")
            step_names = (
                get_resume_steps(sector_id, mode=params.get("mode", "fusion"))
                if sector_id
                else ["monitor_watch"]
            )
            if not step_names:
                step_names = ["monitor_watch"]

        sector_id = params.get("sector_id", "sector_ai_compute")
        ctx: dict[str, Any] = {
            "sector_id": sector_id,
            "focus": params.get("focus"),
            "query": params.get("query"),
            "content": params.get("content"),
            "source_ref": params.get("source_ref", "orchestrator"),
            "mode": params.get("mode", "fusion"),
            "operator": params.get("operator", "analyst"),
            "stop_on_gate": bool(params.get("stop_on_gate")),
        }
        results: list[dict] = []
        for name in step_names:
            yield {"event": "step_start", "data": {"step": name}}
            handler = STEP_HANDLERS.get(name)
            if handler is None:
                entry = {"step": name, "status": "unknown_step"}
                results.append(entry)
                yield {"event": "step_done", "data": entry}
                continue
            if name in GATED_STEPS and not is_sector_confirmed(sector_id):
                entry = {
                    "step": name,
                    "status": "skipped",
                    "reason": "sector_not_confirmed",
                    "required_action": "ConfirmSectorBeta",
                }
                results.append(entry)
                yield {"event": "step_done", "data": entry}
                if ctx.get("stop_on_gate"):
                    break
                continue
            try:
                output = handler(ctx)
                status = output.get("status", "ok")
                spec = get_agent_spec(name) or {}
                entry = {
                    "step": name,
                    "status": status,
                    "agent_class": spec.get("agent_class"),
                    "runtime": spec.get("runtime"),
                    "output": output,
                }
                results.append(entry)
                yield {"event": "step_done", "data": {"step": name, "status": status}}
                if status == "ok":
                    for block in build_ui_blocks(name, output):
                        fb = _yield_block(block, operator)
                        if fb:
                            yield {"event": "block", "data": fb}
            except WorkflowGateError as e:
                entry = {"step": name, "status": "skipped", "reason": e.code, "message": e.message}
                results.append(entry)
                yield {"event": "step_done", "data": entry}
                if ctx.get("stop_on_gate"):
                    break
            except Exception as e:
                entry = {"step": name, "status": "error", "error": str(e)}
                results.append(entry)
                yield {"event": "step_done", "data": entry}
                if ctx.get("stop_on_gate"):
                    break

        completed = sum(1 for r in results if r.get("status") in ("ok", "skipped"))
        final = {
            "pipeline_id": f"pipe_{uuid.uuid4().hex[:12]}",
            "agent": "invest_research_orchestrator_v1",
            "sector_id": sector_id,
            "sector_confirmed": is_sector_confirmed(sector_id),
            "steps_requested": step_names,
            "steps_completed": completed,
            "results": results,
            "disclaimer": "流水线产出均为提案/草稿，须经 Ontology Action 人工确认",
            "agent_summary": f"流水线完成 {completed}/{len(step_names)} 步",
        }
        enriched = attach_ui_blocks("orchestrator", final, operator=operator)
        for block in enriched.get("ui_blocks") or []:
            if block.get("type") in ("pipeline_steps", "workflow_progress", "metric_cards"):
                yield {"event": "block", "data": block}
        yield {"event": "run_complete", "data": enriched}
        return

    result = _run_agent_sync(agent_key, params)
    enriched = attach_ui_blocks(agent_key, result, operator=operator)
    for block in enriched.get("ui_blocks") or []:
        yield {"event": "block", "data": block}
    yield {"event": "run_complete", "data": enriched}


def iter_session_message_stream(
    *,
    message: str,
    intent: dict[str, Any],
    stream_assistant: bool = True,
    operator: str = "analyst",
) -> Generator[str, None, None]:
    yield sse_encode("intent", intent)

    assistant = intent.get("assistant_message") or ""
    if stream_assistant and assistant:
        for chunk in iterate_text_chunks(assistant, chunk_size=4):
            yield sse_encode("message_delta", {"content": chunk})
        yield sse_encode("message_done", {})

    if intent.get("intent") == "navigate":
        yield sse_encode("done", {"navigate": intent.get("params", {}).get("route")})
        return

    if intent.get("intent") not in ("run_agent",) or not intent.get("agent_key"):
        yield sse_encode("done", {})
        return

    agent_key = intent["agent_key"]
    params = intent.get("params") or {}
    try:
        for item in iter_agent_run_events(agent_key, params, operator=operator):
            yield sse_encode(item["event"], item["data"])
            if item["event"] == "run_complete":
                summary = item["data"].get("agent_summary")
                if summary and stream_assistant:
                    yield sse_encode("summary_start", {})
                    for chunk in iterate_text_chunks(summary, chunk_size=6):
                        yield sse_encode("summary_delta", {"content": chunk})
                    yield sse_encode("summary_done", {})
        yield sse_encode("done", {})
    except Exception as e:
        yield sse_encode("error", {"detail": str(e)})
