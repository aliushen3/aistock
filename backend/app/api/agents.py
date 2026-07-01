from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.registry import enrich_agent_response, list_agent_matrix
from app.agents.bearcase_agent import run_bearcase_agent
from app.agents.bottleneck_scout_agent import run_bottleneck_scout_agent
from app.agents.candidate_fusion_agent import run_candidate_fusion_agent
from app.agents.data_source_agent import run_data_source_agent
from app.agents.data_source_pipeline import list_data_source_pipeline_presets, run_data_source_pipeline
from app.agents.knowledge_ingest_agent import run_knowledge_ingest_agent
from app.agents.monitor_watch_agent import run_monitor_watch_agent
from app.agents.orchestrator import run_invest_research_orchestrator
from app.agents.report_graphrag_agent import run_report_graphrag_agent
from app.agents.sector_recommend_agent import run_sector_recommend_agent
from app.agents.serenity_path_agent import run_serenity_path_agent
from app.services.bearcase_store import list_bear_cases
from app.services.bottleneck_recommendations import list_recommendations as list_bottleneck_recs
from app.services.bottleneck_recommendations import update_status as update_bottleneck_status
from app.services.sector_adopt import adopt_recommendation, dismiss_recommendation
from app.services.sector_recommendations import list_recommendations
from app.services.serenity_adopt import confirm_recommendation as confirm_serenity
from app.services.serenity_adopt import dismiss_recommendation as dismiss_serenity
from app.services.serenity_recommendations import list_recommendations as list_serenity_recs
from app.services.watchlist_service import build_dynamic_watchlist

router = APIRouter(prefix="/agents", tags=["agents"])


class SectorRecommendRequest(BaseModel):
    focus: str | None = Field(None, description="关注方向，如 AI算力、机器人")
    query: str | None = Field(None, description="补充研究问题")
    max_recommendations: int = Field(5, ge=1, le=10)
    operator: str = "analyst"
    force_cold_start: bool = Field(
        False, description="强制走行业板块综合排序（多日涨幅+资金净流入+题材热度），无视已有赛道"
    )


class KnowledgeIngestRequest(BaseModel):
    sector_id: str
    source_type: str = "research_report"
    source_ref: str
    content: str = Field(..., min_length=20)
    operator: str = "analyst"


class BottleneckScoutRequest(BaseModel):
    sector_id: str
    min_hint_level: str = Field("hint_medium", description="hint_low | hint_medium | hint_high")
    operator: str = "analyst"


class OrchestratorRequest(BaseModel):
    sector_id: str = "sector_ai_compute"
    focus: str | None = None
    query: str | None = None
    content: str | None = None
    source_ref: str = "orchestrator"
    mode: str = "fusion"
    steps: list[str] | None = None
    stop_on_gate: bool = False
    operator: str = "analyst"
    data_task: str | None = Field(None, description="data_source_fetch 步骤任务类型")
    data_tasks: list[str] | None = Field(None, description="data_source_pipeline 多任务列表")
    data_preset: str | None = Field(None, description="sector_scan|ods_warmup|full_collection|valuation_pass")
    sync_ods: bool = False
    data_limit: int = Field(20, ge=1, le=100)
    stock_code: str | None = None
    stop_on_error: bool = False


class SerenityPathRequest(BaseModel):
    sector_id: str
    min_serenity_hint: float = Field(50.0, ge=0, le=100)
    operator: str = "analyst"


class ReportGraphRAGRequest(BaseModel):
    sector_id: str
    mode: str = "fusion"
    operator: str = "analyst"


class CandidateFusionRequest(BaseModel):
    sector_id: str
    mode: str = "fusion"
    operator: str = "analyst"


class MonitorWatchRequest(BaseModel):
    sector_id: str | None = None
    mode: str = "fusion"
    operator: str = "analyst"


class BearCaseRequest(BaseModel):
    sector_id: str
    mode: str = "fusion"
    operator: str = "analyst"


class DataSourceFetchRequest(BaseModel):
    task: str = Field(
        "valuation",
        description="valuation|quote|research|signal|news|fundamental|announcement|sector_scan",
    )
    stock_code: str | None = None
    stock_codes: list[str] | None = None
    sector_id: str | None = None
    sync_ods: bool = False
    limit: int = Field(20, ge=1, le=100)
    operator: str = "analyst"


class DataSourcePipelineRequest(BaseModel):
    sector_id: str
    preset: str | None = Field(None, description="sector_scan|ods_warmup|full_collection|valuation_pass")
    tasks: list[str] | None = None
    sync_ods: bool | None = None
    stock_code: str | None = None
    limit: int = Field(20, ge=1, le=100)
    stop_on_error: bool = False
    operator: str = "analyst"


@router.get("/matrix")
def get_agent_matrix():
    """Agent 矩阵 A/B 分类（F6）。"""
    return {"items": list_agent_matrix(), "note": "A 类真 LLM；B 类确定性 Pipeline（LLM 仅兜底/解释）"}


@router.get("/watchlist")
def get_dynamic_watchlist(focus: str | None = None):
    """动态观察清单（C7）：研报主题 + Ontology + ODS/上传元数据。"""
    return build_dynamic_watchlist(focus=focus, refresh=True)


@router.post("/sector-recommend/run")
def run_sector_recommend(req: SectorRecommendRequest):
    """运行赛道推荐智能体：工具采集 → LLM/规则推理 → 提案落库。"""
    return enrich_agent_response(
        "sector_recommend",
        run_sector_recommend_agent(
            focus=req.focus,
            query=req.query,
            max_recommendations=req.max_recommendations,
            operator=req.operator,
            force_cold_start=req.force_cold_start,
        ),
    )


@router.post("/knowledge-ingest/run")
def run_knowledge_ingest(req: KnowledgeIngestRequest):
    """运行知识抽取智能体：ReAct 工具 + 规则/LLM 抽取 → 知识草案。"""
    try:
        return enrich_agent_response(
            "knowledge_ingest",
            run_knowledge_ingest_agent(
                sector_id=req.sector_id,
                source_type=req.source_type,
                source_ref=req.source_ref,
                content=req.content,
                operator=req.operator,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/bottleneck-scout/run")
def run_bottleneck_scout(req: BottleneckScoutRequest):
    try:
        return enrich_agent_response(
            "bottleneck_scout",
            run_bottleneck_scout_agent(
                sector_id=req.sector_id,
                min_hint_level=req.min_hint_level,
                operator=req.operator,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/bottleneck-recommendations")
def get_bottleneck_recommendations(sector_id: str | None = None, status: str | None = None):
    return {"items": list_bottleneck_recs(sector_id=sector_id, status=status)}


@router.post("/bottleneck-recommendations/{rec_id}/dismiss")
def dismiss_bottleneck_recommendation(rec_id: str):
    rec = update_bottleneck_status(rec_id, "dismissed")
    if rec is None:
        raise HTTPException(status_code=404, detail="提案不存在")
    return rec


@router.post("/orchestrator/run")
def run_orchestrator(req: OrchestratorRequest):
    try:
        return enrich_agent_response(
            "orchestrator",
            run_invest_research_orchestrator(
                sector_id=req.sector_id,
                focus=req.focus,
                query=req.query,
                content=req.content,
                source_ref=req.source_ref,
                mode=req.mode,
                steps=req.steps,
                operator=req.operator,
                stop_on_gate=req.stop_on_gate,
                data_task=req.data_task,
                data_tasks=req.data_tasks,
                data_preset=req.data_preset,
                sync_ods=req.sync_ods,
                data_limit=req.data_limit,
                stock_code=req.stock_code,
                stop_on_error=req.stop_on_error,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/serenity-path/run")
def run_serenity_path(req: SerenityPathRequest):
    try:
        return enrich_agent_response(
            "serenity_path",
            run_serenity_path_agent(
                sector_id=req.sector_id,
                min_serenity_hint=req.min_serenity_hint,
                operator=req.operator,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/serenity-recommendations")
def get_serenity_recommendations(sector_id: str | None = None, status: str | None = None):
    return {"items": list_serenity_recs(sector_id=sector_id, status=status)}


@router.post("/serenity-recommendations/{rec_id}/confirm")
def confirm_serenity_recommendation(rec_id: str, operator: str = "analyst", reason: str = ""):
    try:
        return confirm_serenity(rec_id, operator=operator, reason=reason or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/serenity-recommendations/{rec_id}/dismiss")
def dismiss_serenity_recommendation(rec_id: str, operator: str = "analyst"):
    try:
        return dismiss_serenity(rec_id, operator=operator)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/report-graphrag/run")
def run_report_graphrag(req: ReportGraphRAGRequest):
    try:
        return enrich_agent_response(
            "report_graphrag",
            run_report_graphrag_agent(
                sector_id=req.sector_id,
                mode=req.mode,
                operator=req.operator,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/candidate-fusion/run")
def run_candidate_fusion(req: CandidateFusionRequest):
    try:
        return enrich_agent_response(
            "candidate_fusion",
            run_candidate_fusion_agent(
                sector_id=req.sector_id,
                mode=req.mode,
                operator=req.operator,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/bear-case/run")
def run_bear_case(req: BearCaseRequest):
    """运行看空对抗智能体：独立检索 → 生成等强空头论点 → 落库（未回应阻断入池）。"""
    try:
        return enrich_agent_response(
            "bear_case",
            run_bearcase_agent(sector_id=req.sector_id, mode=req.mode, operator=req.operator),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/bear-cases")
def get_bear_cases(sector_id: str | None = None, stock_code: str | None = None, status: str | None = None):
    return {"items": list_bear_cases(sector_id=sector_id, stock_code=stock_code, status=status)}


@router.post("/monitor-watch/run")
def run_monitor_watch(req: MonitorWatchRequest):
    return enrich_agent_response(
        "monitor_watch",
        run_monitor_watch_agent(
            sector_id=req.sector_id,
            mode=req.mode,
            operator=req.operator,
        ),
    )


@router.post("/data-source-fetch/run")
def run_data_source_fetch(req: DataSourceFetchRequest):
    """数据源获取智能体：七层任务路由 + 分层拉取 + 可选 ODS 同步。"""
    try:
        return enrich_agent_response(
            "data_source_fetch",
            run_data_source_agent(
                task=req.task,
                stock_code=req.stock_code,
                stock_codes=req.stock_codes,
                sector_id=req.sector_id,
                sync_ods=req.sync_ods,
                limit=req.limit,
                operator=req.operator,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/data-source-pipeline/presets")
def get_data_source_pipeline_presets():
    return {"items": list_data_source_pipeline_presets()}


@router.post("/data-source-pipeline/run")
def run_data_source_pipeline_api(req: DataSourcePipelineRequest):
    """七层数据源采集 Pipeline：多任务顺序执行 + 可选 ODS 全层同步。"""
    try:
        return enrich_agent_response(
            "data_source_pipeline",
            run_data_source_pipeline(
                req.sector_id,
                tasks=req.tasks,
                preset=req.preset,
                sync_ods=req.sync_ods,
                stock_code=req.stock_code,
                limit=req.limit,
                operator=req.operator,
                stop_on_error=req.stop_on_error,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/sector-recommendations")
def get_sector_recommendations(status: str | None = None, limit: int = 20):
    return {"items": list_recommendations(status=status, limit=limit)}


@router.post("/sector-recommendations/{rec_id}/adopt")
def adopt_sector_recommendation(rec_id: str, operator: str = "analyst", auto_bootstrap: bool = True):
    """采纳推荐：新赛道写入 ont_sector（beta_candidate），可选自动冷启动。"""
    try:
        return adopt_recommendation(rec_id, operator=operator, auto_bootstrap=auto_bootstrap)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class SectorBootstrapRequest(BaseModel):
    sector_id: str
    sync_constituents: bool = True
    ingest_reports: bool = True


@router.post("/sector-bootstrap/run")
def run_sector_bootstrap(req: SectorBootstrapRequest):
    """手动触发赛道冷启动（成分股 + 研报草案）。"""
    from app.services.sector_bootstrap import bootstrap_sector

    try:
        return bootstrap_sector(
            req.sector_id,
            sync_constituents=req.sync_constituents,
            ingest_reports=req.ingest_reports,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sector-recommendations/{rec_id}/dismiss")
def dismiss_sector_recommendation(rec_id: str, operator: str = "analyst"):
    try:
        return dismiss_recommendation(rec_id, operator=operator)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
