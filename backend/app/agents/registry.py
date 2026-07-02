"""投研 Agent 矩阵 A/B 分类注册表（DESIGN §3.4 / F6）。"""

from __future__ import annotations

from typing import Any

AGENT_MATRIX: dict[str, dict[str, Any]] = {
    "knowledge_ingest": {
        "display_name": "KnowledgeIngestAgent",
        "agent_class": "A",
        "runtime": "react",
        "llm_required": True,
        "llm_assisted_default": True,
        "invest_step": "Step2 拓扑构建",
        "proposal": "KnowledgeDraft",
        "action": "CalibrateChain",
    },
    "report_graphrag": {
        "display_name": "ReportGraphRAGAgent",
        "agent_class": "A",
        "runtime": "pipeline",
        "llm_required": True,
        "llm_assisted_default": True,
        "invest_step": "Step5 看多论证",
        "proposal": "ResearchReport(draft)",
        "action": "PublishReport",
    },
    "bear_case": {
        "display_name": "BearCaseAgent",
        "agent_class": "A",
        "runtime": "pipeline",
        "llm_required": False,
        "llm_assisted_default": True,
        "invest_step": "Step5' 看空对抗",
        "proposal": "BearCase",
        "action": "RebutBearCase",
    },
    "sector_recommend": {
        "display_name": "SectorRecommendAgent",
        "agent_class": "B",
        "runtime": "pipeline",
        "llm_required": False,
        "llm_assisted_default": False,
        "invest_step": "Step1 赛道发现",
        "proposal": "SectorRecommendation",
        "action": "ConfirmSectorBeta",
    },
    "sector_bootstrap": {
        "display_name": "SectorBootstrap",
        "agent_class": "B",
        "runtime": "pipeline",
        "llm_required": False,
        "llm_assisted_default": False,
        "invest_step": "Step1' 赛道冷启动",
        "proposal": "ConstituentSync+KnowledgeDraft",
        "action": None,
    },
    "bottleneck_scout": {
        "display_name": "BottleneckScoutAgent",
        "agent_class": "B",
        "runtime": "pipeline",
        "llm_required": False,
        "llm_assisted_default": False,
        "invest_step": "Step3 瓶颈扫描",
        "proposal": "BottleneckRecommendation",
        "action": "ConfirmBottleneck",
    },
    "serenity_path": {
        "display_name": "SerenityPathAgent",
        "agent_class": "B",
        "runtime": "pipeline",
        "llm_required": False,
        "llm_assisted_default": False,
        "invest_step": "Step4 逆向溯源",
        "proposal": "SerenityPath",
        "action": "ConfirmSerenityNiche",
    },
    "candidate_fusion": {
        "display_name": "CandidateFusionAgent",
        "agent_class": "B",
        "runtime": "pipeline",
        "llm_required": False,
        "llm_assisted_default": False,
        "invest_step": "Step6 候选融合",
        "proposal": "CandidatePoolEntry",
        "action": "ApprovePoolEntry",
    },
    "monitor_watch": {
        "display_name": "MonitorWatchAgent",
        "agent_class": "B",
        "runtime": "pipeline",
        "llm_required": False,
        "llm_assisted_default": False,
        "invest_step": "Step7 动态监控",
        "proposal": "Alert",
        "action": "ConfirmBottleneckEasing",
    },
    "orchestrator": {
        "display_name": "InvestResearchOrchestrator",
        "agent_class": "B",
        "runtime": "pipeline",
        "llm_required": False,
        "llm_assisted_default": False,
        "invest_step": "一键投研",
        "proposal": "PipelineRun",
        "action": None,
    },
    "data_source_fetch": {
        "display_name": "DataSourceFetchAgent",
        "agent_class": "B",
        "runtime": "pipeline",
        "llm_required": False,
        "llm_assisted_default": False,
        "invest_step": "数据采集",
        "proposal": "LayerFetchResult",
        "action": None,
    },
    "data_source_pipeline": {
        "display_name": "DataSourcePipeline",
        "agent_class": "B",
        "runtime": "pipeline",
        "llm_required": False,
        "llm_assisted_default": False,
        "invest_step": "数据采集 Pipeline",
        "proposal": "PipelineRun",
        "action": None,
    },
}


def get_agent_spec(agent_key: str) -> dict | None:
    return AGENT_MATRIX.get(agent_key)


def list_agent_matrix() -> list[dict]:
    items = []
    for key, spec in AGENT_MATRIX.items():
        items.append({"agent_key": key, **spec})
    return items


def enrich_agent_response(
    agent_key: str,
    payload: dict,
    llm_assisted: bool | None = None,
    operator: str | None = None,
) -> dict:
    from app.services.request_context import get_current_operator

    op = operator or get_current_operator()
    spec = AGENT_MATRIX.get(agent_key, {})
    assisted = (
        llm_assisted
        if llm_assisted is not None
        else payload.get("llm_assisted", spec.get("llm_assisted_default", False))
    )
    enriched = dict(payload)
    enriched["agent_key"] = agent_key
    enriched["agent_class"] = spec.get("agent_class", "B")
    enriched["runtime"] = spec.get("runtime", "pipeline")
    enriched["llm_assisted"] = assisted
    enriched["display_name"] = spec.get("display_name", agent_key)
    from app.services.agent_ui_blocks import attach_ui_blocks

    return attach_ui_blocks(agent_key, enriched, operator=op)
