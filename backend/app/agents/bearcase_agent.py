"""BearCase 看空对抗智能体（主线一，A 类真 LLM 智能体）。

独立检索反面证据，对融合池候选生成等强度看空论点，持久化为提案；
高 severity 未回应将阻断入池（见 action_executor 三道闸闸三）。
对齐 docs/DESIGN.md §3.4 / §6.4。
"""

from __future__ import annotations

from app.services.bearcase import generate_and_store_bear_cases
from app.services.graph_store import get_store
from app.services.workflow import is_sector_confirmed


def run_bearcase_agent(
    sector_id: str,
    mode: str = "fusion",
    operator: str = "analyst",
) -> dict:
    store = get_store()
    if store.get_sector(sector_id) is None:
        raise ValueError(f"赛道不存在: {sector_id}")

    result = generate_and_store_bear_cases(sector_id, mode, operator=operator)
    high = result["high_unrebutted"]

    return {
        "run_id": result["run_id"],
        "agent": "bear_case_v1",
        "agent_mode": result["agent_mode"],
        "sector_id": sector_id,
        "sector_confirmed": is_sector_confirmed(sector_id),
        "mode": mode,
        "operator": operator,
        "bear_case_count": result["bear_case_count"],
        "high_unrebutted": high,
        "agent_summary": (
            f"生成 {result['bear_case_count']} 条看空论点，其中 {high} 条高severity 待回应"
            "（未回应将阻断入池）"
        ),
        "bear_cases": result["bear_cases"],
        "disclaimer": "看空论点供等强对抗，须研究员 RebutBearCase 回应，不构成投资建议",
    }
