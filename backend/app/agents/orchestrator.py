"""投研七步 Orchestrator — 按门控串联各 Agent。"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from app.agents.bearcase_agent import run_bearcase_agent
from app.agents.bottleneck_scout_agent import run_bottleneck_scout_agent
from app.agents.candidate_fusion_agent import run_candidate_fusion_agent
from app.agents.data_source_agent import run_data_source_agent
from app.agents.data_source_pipeline import run_data_source_pipeline
from app.agents.knowledge_ingest_agent import run_knowledge_ingest_agent
from app.agents.monitor_watch_agent import run_monitor_watch_agent
from app.agents.registry import get_agent_spec
from app.agents.report_graphrag_agent import run_report_graphrag_agent
from app.agents.sector_recommend_agent import run_sector_recommend_agent
from app.agents.serenity_path_agent import run_serenity_path_agent
from app.services.graph_store import get_store
from app.services.sector_bootstrap import bootstrap_sector
from app.services.ods_service import sync_all_ods_layers
from app.services.workflow import WorkflowGateError, is_sector_confirmed, require_sector_confirmed

DEFAULT_STEPS = [
    "sector_recommend",
    "sector_bootstrap",
    "knowledge_ingest",
    "bottleneck_scout",
    "serenity_path",
    "report_graphrag",
    "bear_case",
    "candidate_fusion",
    "monitor_watch",
]

GATED_STEPS = {
    "bottleneck_scout",
    "serenity_path",
    "report_graphrag",
    "bear_case",
    "candidate_fusion",
}


def _step_sector_recommend(ctx: dict) -> dict:
    return run_sector_recommend_agent(
        focus=ctx.get("focus"),
        query=ctx.get("query"),
        max_recommendations=ctx.get("max_recommendations", 3),
        operator=ctx.get("operator", "analyst"),
    )


def _step_sector_bootstrap(ctx: dict) -> dict:
    return bootstrap_sector(
        ctx["sector_id"],
        sync_constituents=ctx.get("bootstrap_constituents", True),
        ingest_reports=ctx.get("bootstrap_reports", True),
    )


def _step_knowledge_ingest(ctx: dict) -> dict:
    content = ctx.get("content")
    if not content or len(content.strip()) < 20:
        return {"status": "skipped", "reason": "no_content"}
    return run_knowledge_ingest_agent(
        sector_id=ctx["sector_id"],
        source_type=ctx.get("source_type", "research_report"),
        source_ref=ctx.get("source_ref", "orchestrator"),
        content=content,
        operator=ctx.get("operator", "analyst"),
    )


def _step_bottleneck_scout(ctx: dict) -> dict:
    require_sector_confirmed(ctx["sector_id"])
    return run_bottleneck_scout_agent(
        sector_id=ctx["sector_id"],
        operator=ctx.get("operator", "analyst"),
    )


def _step_serenity_path(ctx: dict) -> dict:
    require_sector_confirmed(ctx["sector_id"])
    return run_serenity_path_agent(
        sector_id=ctx["sector_id"],
        operator=ctx.get("operator", "analyst"),
    )


def _step_report_graphrag(ctx: dict) -> dict:
    require_sector_confirmed(ctx["sector_id"])
    return run_report_graphrag_agent(
        sector_id=ctx["sector_id"],
        mode=ctx.get("mode", "fusion"),
        operator=ctx.get("operator", "analyst"),
    )


def _step_candidate_fusion(ctx: dict) -> dict:
    require_sector_confirmed(ctx["sector_id"])
    return run_candidate_fusion_agent(
        sector_id=ctx["sector_id"],
        mode=ctx.get("mode", "fusion"),
        operator=ctx.get("operator", "analyst"),
    )


def _step_bear_case(ctx: dict) -> dict:
    require_sector_confirmed(ctx["sector_id"])
    return run_bearcase_agent(
        sector_id=ctx["sector_id"],
        mode=ctx.get("mode", "fusion"),
        operator=ctx.get("operator", "analyst"),
    )


def _step_monitor_watch(ctx: dict) -> dict:
    return run_monitor_watch_agent(
        sector_id=ctx["sector_id"],
        mode=ctx.get("mode", "fusion"),
        operator=ctx.get("operator", "analyst"),
    )


def _step_data_source_fetch(ctx: dict) -> dict:
    task = ctx.get("data_task") or "sector_scan"
    return run_data_source_agent(
        task=task,
        stock_code=ctx.get("stock_code"),
        sector_id=ctx["sector_id"],
        sync_ods=bool(ctx.get("sync_ods")),
        limit=int(ctx.get("data_limit") or 20),
        operator=ctx.get("operator", "analyst"),
    )


def _step_data_source_ods_sync(ctx: dict) -> dict:
    return sync_all_ods_layers(ctx["sector_id"])


def _step_data_source_pipeline(ctx: dict) -> dict:
    return run_data_source_pipeline(
        ctx["sector_id"],
        tasks=ctx.get("data_tasks"),
        preset=ctx.get("data_preset"),
        sync_ods=ctx.get("sync_ods"),
        stock_code=ctx.get("stock_code"),
        limit=int(ctx.get("data_limit") or 20),
        operator=ctx.get("operator", "analyst"),
        stop_on_error=bool(ctx.get("stop_on_error")),
    )


STEP_HANDLERS: dict[str, Callable[[dict], dict]] = {
    "sector_recommend": _step_sector_recommend,
    "sector_bootstrap": _step_sector_bootstrap,
    "knowledge_ingest": _step_knowledge_ingest,
    "bottleneck_scout": _step_bottleneck_scout,
    "serenity_path": _step_serenity_path,
    "report_graphrag": _step_report_graphrag,
    "bear_case": _step_bear_case,
    "candidate_fusion": _step_candidate_fusion,
    "monitor_watch": _step_monitor_watch,
    "data_source_fetch": _step_data_source_fetch,
    "data_source_ods_sync": _step_data_source_ods_sync,
    "data_source_pipeline": _step_data_source_pipeline,
}


def run_invest_research_orchestrator(
    sector_id: str,
    focus: str | None = None,
    query: str | None = None,
    content: str | None = None,
    source_ref: str = "orchestrator",
    mode: str = "fusion",
    steps: list[str] | None = None,
    operator: str = "analyst",
    stop_on_gate: bool = False,
    data_task: str | None = None,
    data_tasks: list[str] | None = None,
    data_preset: str | None = None,
    sync_ods: bool = False,
    data_limit: int = 20,
    stock_code: str | None = None,
    stop_on_error: bool = False,
) -> dict:
    step_names = steps or DEFAULT_STEPS
    store = get_store()
    needs_sector = any(name != "sector_recommend" for name in step_names)
    if needs_sector and store.get_sector(sector_id) is None:
        raise ValueError(f"赛道不存在: {sector_id}")

    pipeline_id = f"pipe_{uuid.uuid4().hex[:12]}"
    ctx: dict[str, Any] = {
        "sector_id": sector_id,
        "focus": focus,
        "query": query,
        "content": content,
        "source_ref": source_ref,
        "mode": mode,
        "operator": operator,
        "data_task": data_task,
        "data_tasks": data_tasks,
        "data_preset": data_preset,
        "sync_ods": sync_ods,
        "data_limit": data_limit,
        "stock_code": stock_code,
        "stop_on_error": stop_on_error,
    }

    results: list[dict] = []
    for name in step_names:
        handler = STEP_HANDLERS.get(name)
        if handler is None:
            results.append({"step": name, "status": "unknown_step"})
            continue

        if name in GATED_STEPS and not is_sector_confirmed(sector_id):
            entry = {
                "step": name,
                "status": "skipped",
                "reason": "sector_not_confirmed",
                "required_action": "ConfirmSectorBeta",
            }
            results.append(entry)
            if stop_on_gate:
                break
            continue

        try:
            output = handler(ctx)
            status = output.get("status", "ok")
            spec = get_agent_spec(name) or {}
            results.append(
                {
                    "step": name,
                    "status": status,
                    "agent_class": spec.get("agent_class"),
                    "runtime": spec.get("runtime"),
                    "output": output,
                }
            )
        except WorkflowGateError as e:
            results.append(
                {
                    "step": name,
                    "status": "skipped",
                    "reason": e.code,
                    "message": e.message,
                }
            )
            if stop_on_gate:
                break
        except Exception as e:
            results.append({"step": name, "status": "error", "error": str(e)})
            if stop_on_gate:
                break

    completed = sum(1 for r in results if r.get("status") in ("ok", "skipped"))
    return {
        "pipeline_id": pipeline_id,
        "agent": "invest_research_orchestrator_v1",
        "sector_id": sector_id,
        "sector_confirmed": is_sector_confirmed(sector_id),
        "steps_requested": step_names,
        "steps_completed": completed,
        "results": results,
        "disclaimer": "流水线产出均为提案/草稿，须经 Ontology Action 人工确认",
    }
