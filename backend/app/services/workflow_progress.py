"""投研工作流进度聚合 — 供首页驾驶舱与断点续跑。

引擎层保留七步（每步一个 Agent + 一个人工 Action，门控粒度不变）；
呈现层聚合为五阶段，对齐分析师心智「赛道 → 产业链 → 环节 → 标的 → 跟踪」：

  阶段① 赛道确认        = Step1
  阶段② 产业链构建      = Step2
  阶段③ 环节挖掘        = Step3 + Step4（瓶颈与 Serenity 双视角并行）
  阶段④ 标的论证与入池  = Step5 + Step6（多空对照 + 三道闸，报告为产出物）
  阶段⑤ 持续跟踪        = Step7
"""

from __future__ import annotations

from app.ontology.object_store import get_product, query_object_set
from app.services.bearcase_store import list_bear_cases
from app.services.bottleneck_recommendations import list_recommendations as list_bottleneck_recs
from app.services.candidate_pool import build_pool
from app.services.extraction import list_drafts
from app.services.graph_store import get_store, sector_company_codes
from app.services.serenity_recommendations import list_recommendations as list_serenity_recs
from app.services.workflow import is_sector_confirmed

STEP_DEFS = [
    {
        "id": "confirm_sector",
        "step_number": 1,
        "title": "确认赛道景气",
        "agent": "SectorRecommendAgent",
        "cta_action": "ConfirmSectorBeta",
        "cta_route": "/",
    },
    {
        "id": "build_topology",
        "step_number": 2,
        "title": "构建产业拓扑",
        "agent": "KnowledgeIngestAgent",
        "cta_action": "CalibrateChain",
        "cta_route": "/knowledge",
    },
    {
        "id": "confirm_bottleneck",
        "step_number": 3,
        "title": "瓶颈扫描确认",
        "agent": "BottleneckScoutAgent",
        "cta_action": "ConfirmBottleneck",
        "cta_route": "/graph",
    },
    {
        "id": "serenity_path",
        "step_number": 4,
        "title": "Serenity 路径",
        "agent": "SerenityPathAgent",
        "cta_action": "ConfirmSerenityNiche",
        "cta_route": "/graph",
    },
    {
        "id": "bull_bear",
        "step_number": 5,
        "title": "看多看空论证",
        "agent": "ReportGraphRAGAgent",
        "cta_action": "PublishReport",
        "cta_route": "/report",
    },
    {
        "id": "candidate_pool",
        "step_number": 6,
        "title": "候选融合入池",
        "agent": "CandidateFusionAgent",
        "cta_action": "ApprovePoolEntry",
        "cta_route": "/candidates",
    },
    {
        "id": "monitor",
        "step_number": 7,
        "title": "动态监控",
        "agent": "MonitorWatchAgent",
        "cta_action": "MonitorRefresh",
        "cta_route": "/dashboard",
    },
]

PHASE_DEFS = [
    {
        "phase_number": 1,
        "id": "phase_sector",
        "title": "赛道确认",
        "description": "发现景气赛道并人工确认",
        "step_numbers": [1],
        "cta_route": "/",
    },
    {
        "phase_number": 2,
        "id": "phase_topology",
        "title": "产业链构建",
        "description": "知识抽取、拓扑校准与成分股",
        "step_numbers": [2],
        "cta_route": "/knowledge",
    },
    {
        "phase_number": 3,
        "id": "phase_segments",
        "title": "环节挖掘",
        "description": "瓶颈与 Serenity 双视角并行扫描确认",
        "step_numbers": [3, 4],
        "cta_route": "/graph",
    },
    {
        "phase_number": 4,
        "id": "phase_thesis",
        "title": "标的论证与入池",
        "description": "多空对照 + 三道闸，报告为产出物",
        "step_numbers": [5, 6],
        "cta_route": "/candidates",
    },
    {
        "phase_number": 5,
        "id": "phase_monitor",
        "title": "持续跟踪",
        "description": "保鲜、瓶颈缓解与组合逻辑健康度",
        "step_numbers": [7],
        "cta_route": "/dashboard",
    },
]


def _aggregate_phases(steps: list[dict]) -> tuple[list[dict], int]:
    """把七步引擎状态聚合为五阶段呈现模型。"""
    by_num = {s["step_number"]: s for s in steps}
    phases: list[dict] = []
    current_phase = 1
    found_active = False
    for spec in PHASE_DEFS:
        members = [by_num[n] for n in spec["step_numbers"] if n in by_num]
        statuses = [m["status"] for m in members]
        if all(s == "done" for s in statuses):
            status = "done"
        elif any(s == "blocked" for s in statuses) and not any(
            s in ("active", "pending") for s in statuses
        ):
            status = "blocked"
        elif any(s in ("active", "blocked") for s in statuses):
            status = "active"
        else:
            status = "pending"
        if status == "active" and not found_active:
            found_active = True
            current_phase = spec["phase_number"]
        block_reason = next((m.get("block_reason") for m in members if m.get("block_reason")), None)
        phases.append(
            {
                "phase_number": spec["phase_number"],
                "id": spec["id"],
                "title": spec["title"],
                "description": spec["description"],
                "cta_route": spec["cta_route"],
                "status": status,
                "block_reason": block_reason,
                "pending_count": sum(m.get("pending_count", 0) for m in members),
                "steps": [m["id"] for m in members],
            }
        )
    if all(p["status"] == "done" for p in phases):
        current_phase = 5
    return phases, current_phase


ORCHESTRATOR_AGENTS = {
    2: ["sector_bootstrap", "knowledge_ingest"],
    3: ["bottleneck_scout"],
    4: ["serenity_path"],
    5: ["report_graphrag", "bear_case"],
    6: ["candidate_fusion"],
    7: ["monitor_watch"],
}


def _count_sector_reports(sector_id: str) -> int:
    from app.services import report as report_service

    count = sum(1 for r in report_service._report_store.values() if r.get("sector_id") == sector_id)
    from app.ontology import pg_store

    if pg_store.is_db_enabled():
        from sqlalchemy import func, select

        from app.db.models import OntResearchReport
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            count = db.scalar(
                select(func.count())
                .select_from(OntResearchReport)
                .where(OntResearchReport.sector_id == sector_id)
            ) or count
        finally:
            db.close()
    return count


def _graph_stats(sector_id: str) -> dict:
    store = get_store()
    products = store.list_products(sector_id)
    companies = sector_company_codes(sector_id)
    pending_drafts = [
        d for d in list_drafts(sector_id) if d.get("status") != "confirmed"
    ]
    return {
        "products": len(products),
        "companies": len(companies),
        "drafts": len(pending_drafts),
    }


def _step1_done(sector_id: str) -> bool:
    return is_sector_confirmed(sector_id)


def _step2_done(sector_id: str, stats: dict) -> bool:
    return stats["products"] >= 1 and stats["drafts"] == 0


def _step3_done(sector_id: str) -> bool:
    store = get_store()
    confirmed = any(
        (get_product(p["id"]) or p).get("bottleneck_status") == "bottleneck_confirmed"
        for p in store.list_products(sector_id)
    )
    if confirmed:
        return True
    pending = list_bottleneck_recs(sector_id=sector_id, status="proposed")
    hints = [
        p
        for p in store.list_products(sector_id)
        if (get_product(p["id"]) or p).get("bottleneck_status") == "bottleneck_hint"
    ]
    return not pending and not hints


def _step4_done(sector_id: str) -> bool:
    store = get_store()
    unconfirmed = []
    for p in store.list_products(sector_id):
        merged = get_product(p["id"]) or p
        if merged.get("serenity_niche") and not merged.get("serenity_niche_confirmed"):
            unconfirmed.append(merged)
    if not unconfirmed:
        return True
    pending = list_serenity_recs(sector_id=sector_id, status="proposed")
    return not pending and not unconfirmed


def _step5_done(sector_id: str) -> bool:
    reports = _count_sector_reports(sector_id)
    bears = list_bear_cases(sector_id=sector_id)
    return reports >= 1 and len(bears) >= 1


def _step6_done(sector_id: str, mode: str = "fusion") -> bool:
    store = get_store()
    pool = build_pool(store, sector_id, mode)
    if not pool:
        return False
    pending = query_object_set(
        "PendingCandidates", filter_extra={"sector_id": sector_id, "mode": mode}
    )
    return len(pending) == 0


def _step7_done(sector_id: str, stats: dict) -> bool:
    if stats["companies"] >= 1:
        return True
    try:
        from app.services.ods_service import list_ods_research_reports

        return len(list_ods_research_reports(sector_id=sector_id, limit=1)) > 0
    except Exception:
        return False


def _evaluate_steps(sector_id: str, mode: str = "fusion") -> tuple[list[dict], int]:
    stats = _graph_stats(sector_id)
    sector_confirmed = _step1_done(sector_id)
    done_flags = [
        sector_confirmed,
        _step2_done(sector_id, stats) if sector_confirmed else False,
        _step3_done(sector_id) if sector_confirmed else False,
        _step4_done(sector_id) if sector_confirmed else False,
        _step5_done(sector_id) if sector_confirmed else False,
        _step6_done(sector_id, mode) if sector_confirmed else False,
        _step7_done(sector_id, stats) if sector_confirmed else False,
    ]

    steps_out: list[dict] = []
    current_step = 1
    found_active = False

    for i, spec in enumerate(STEP_DEFS):
        step_num = spec["step_number"]
        done = done_flags[i]
        block_reason = None
        pending_count = 0

        if not sector_confirmed and step_num > 1:
            status = "blocked"
            block_reason = "须先确认赛道景气（ConfirmSectorBeta）"
        elif done:
            status = "done"
        elif not found_active:
            status = "active"
            found_active = True
            current_step = step_num
        else:
            status = "pending"

        if step_num == 1 and not done:
            pending_count = 0 if sector_confirmed else 1
            block_reason = block_reason or "请研究员确认赛道景气"
        elif step_num == 2:
            pending_count = stats["drafts"]
            if status == "active" and stats["products"] == 0:
                block_reason = "尚无产品节点，请运行 Knowledge Agent 或确认知识草案"
        elif step_num == 3:
            pending_count = len(list_bottleneck_recs(sector_id=sector_id, status="proposed"))
        elif step_num == 4:
            pending_count = len(list_serenity_recs(sector_id=sector_id, status="proposed"))
        elif step_num == 6:
            pending_count = len(
                query_object_set(
                    "PendingCandidates", filter_extra={"sector_id": sector_id, "mode": mode}
                )
            )

        steps_out.append(
            {
                **spec,
                "status": status,
                "block_reason": block_reason,
                "pending_count": pending_count,
            }
        )

    if all(done_flags):
        current_step = 7

    return steps_out, current_step


def _build_pending_todos(sector_id: str, steps: list[dict], stats: dict) -> list[dict]:
    todos: list[dict] = []
    if not _step1_done(sector_id):
        todos.append(
            {
                "type": "sector_not_confirmed",
                "count": 1,
                "message": "赛道尚未确认景气",
                "action": "ConfirmSectorBeta",
                "route": "/",
            }
        )
    if stats["drafts"] > 0:
        todos.append(
            {
                "type": "knowledge_draft",
                "count": stats["drafts"],
                "message": f"{stats['drafts']} 条知识草案待校准确认",
                "action": "CalibrateChain",
                "route": "/knowledge",
            }
        )
    bn = len(list_bottleneck_recs(sector_id=sector_id, status="proposed"))
    if bn:
        todos.append(
            {
                "type": "bottleneck_recommendation",
                "count": bn,
                "message": f"{bn} 条瓶颈提案待确认",
                "action": "ConfirmBottleneck",
                "route": "/graph",
            }
        )
    ser = len(list_serenity_recs(sector_id=sector_id, status="proposed"))
    if ser:
        todos.append(
            {
                "type": "serenity_recommendation",
                "count": ser,
                "message": f"{ser} 条 Serenity 路径待确认",
                "action": "ConfirmSerenityNiche",
                "route": "/graph",
            }
        )
    pending_c = len(
        query_object_set("PendingCandidates", filter_extra={"sector_id": sector_id, "mode": "fusion"})
    )
    if pending_c:
        todos.append(
            {
                "type": "pending_candidates",
                "count": pending_c,
                "message": f"{pending_c} 个候选待人工入池",
                "action": "ApprovePoolEntry",
                "route": "/candidates",
            }
        )
    if stats["products"] == 0 and _step1_done(sector_id):
        todos.append(
            {
                "type": "empty_graph",
                "count": 1,
                "message": "产业图谱为空，请构建拓扑或同步成分股",
                "action": "KnowledgeIngest",
                "route": "/knowledge",
            }
        )
    elif stats["companies"] == 0 and stats["products"] >= 1:
        todos.append(
            {
                "type": "no_constituents",
                "count": 1,
                "message": "尚无成分股，请在知识页/DataOps 配置东财板块并同步",
                "action": "SyncConstituents",
                "route": "/knowledge",
            }
        )

    # 主线一：高severity 空头论点未回应 — 阻断入池，须优先裁决
    unrebutted = list_bear_cases(sector_id=sector_id, status="unrebutted", severity="high")
    if unrebutted:
        todos.append(
            {
                "type": "bear_case_unrebutted",
                "count": len(unrebutted),
                "message": f"{len(unrebutted)} 条高severity空头论点未回应（阻断入池）",
                "action": "RebutBearCase",
                "route": "/candidates",
            }
        )

    # 主线二：保鲜过期知识 — 需复核刷新
    from app.services.freshness import product_freshness

    stale = [
        p
        for p in get_store().list_products(sector_id)
        if product_freshness(get_product(p["id"]) or p)["freshness"] == "stale"
    ]
    if stale:
        todos.append(
            {
                "type": "knowledge_stale",
                "count": len(stale),
                "message": f"{len(stale)} 个环节知识已过期（stale），需复核刷新",
                "action": "RefreshKnowledge",
                "route": "/dashboard",
            }
        )
    return todos


def get_resume_steps(sector_id: str, mode: str = "fusion") -> list[str]:
    """返回 Orchestrator 断点续跑步骤（跳过已完成与须人工步骤）。"""
    steps, _ = _evaluate_steps(sector_id, mode)
    out: list[str] = []
    seen: set[str] = set()
    for s in steps:
        if s["status"] not in ("active", "pending"):
            continue
        for agent in ORCHESTRATOR_AGENTS.get(s["step_number"], []):
            if agent not in seen:
                seen.add(agent)
                out.append(agent)
    return out


def get_sector_workflow_status(sector_id: str, mode: str = "fusion") -> dict:
    store = get_store()
    sector = store.get_sector(sector_id)
    if sector is None:
        raise ValueError(f"赛道不存在: {sector_id}")

    stats = _graph_stats(sector_id)
    steps, current_step = _evaluate_steps(sector_id, mode)
    pending_todos = _build_pending_todos(sector_id, steps, stats)
    phases, current_phase = _aggregate_phases(steps)

    return {
        "sector_id": sector_id,
        "sector_name": sector.get("name"),
        "sector_confirmed": is_sector_confirmed(sector_id),
        "current_step": current_step,
        "steps": steps,
        "current_phase": current_phase,
        "phases": phases,
        "pending_todos": pending_todos,
        "resume_steps": get_resume_steps(sector_id, mode),
        "graph_stats": stats,
    }


def get_workflow_overview(mode: str = "fusion") -> list[dict]:
    """全部赛道的工作流概览 — 首页驾驶舱赛道看板数据源。"""
    store = get_store()
    overview: list[dict] = []
    for sector in store.list_sectors():
        sector_id = sector["id"]
        try:
            status = get_sector_workflow_status(sector_id, mode=mode)
        except Exception:
            continue
        active_phase = next(
            (p for p in status["phases"] if p["phase_number"] == status["current_phase"]),
            None,
        )
        overview.append(
            {
                "sector_id": sector_id,
                "sector_name": status.get("sector_name"),
                "sector_confirmed": status["sector_confirmed"],
                "current_phase": status["current_phase"],
                "phases": status["phases"],
                "blocking_point": (active_phase or {}).get("block_reason"),
                "pending_total": sum(t.get("count", 0) for t in status["pending_todos"]),
                "pending_todos": status["pending_todos"],
                "resume_steps": status["resume_steps"],
            }
        )
    return overview
