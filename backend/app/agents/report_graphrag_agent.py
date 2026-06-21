"""GraphRAG 报告论证智能体 — 生成投研逻辑草稿。"""

from __future__ import annotations

import uuid

from app.services import report as report_service
from app.services.graph_store import get_store
from app.services.workflow import is_sector_confirmed


def run_report_graphrag_agent(
    sector_id: str,
    mode: str = "fusion",
    operator: str = "analyst",
) -> dict:
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise ValueError(f"赛道不存在: {sector_id}")

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    report = report_service.generate_report(store, sector_id, mode, use_graphrag=True)

    chain_steps = len(report.get("logic_chain", []))
    citation_count = len(report.get("citations", []))
    counter_count = len(report.get("counter_arguments", []))
    unverified = len(report.get("unverified_claims", []))

    return {
        "run_id": run_id,
        "agent": "report_graphrag_v1",
        "agent_mode": report.get("generated_by", "graphrag_hybrid_v1"),
        "sector_id": sector_id,
        "sector_confirmed": is_sector_confirmed(sector_id),
        "report_id": report["report_id"],
        "status": report["status"],
        "mode": mode,
        "operator": operator,
        "agent_summary": (
            f"已生成 GraphRAG 草稿 {report['report_id']}："
            f"{chain_steps} 步逻辑链、{citation_count} 条引用、"
            f"{counter_count} 项反证"
            + (f"、{unverified} 条待核实" if unverified else "")
        ),
        "report": {
            "report_id": report["report_id"],
            "status": report["status"],
            "generated_by": report.get("generated_by"),
            "logic_chain_steps": chain_steps,
            "citation_count": citation_count,
            "counter_argument_count": counter_count,
            "unverified_count": unverified,
            "candidate_count": len(report.get("candidates", [])),
        },
        "disclaimer": report.get("disclaimer"),
    }
