"""LUI 意图路由 — P0 规则引擎。"""

from __future__ import annotations

import re
from typing import Any


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def parse_intent(
    message: str,
    *,
    sector_id: str | None = None,
    focus: str | None = None,
    workflow_step: int | None = None,
) -> dict[str, Any]:
    msg = message.strip()
    low = _norm(msg)

    if not msg:
        return {
            "intent": "clarify",
            "assistant_message": "请输入投研意图，例如：扫描景气赛道、从断点继续、扫描瓶颈。",
            "suggested_chips": ["发现景气赛道", "从断点继续", "扫描瓶颈"],
        }

    # 断点续跑
    if any(k in low for k in ("断点", "继续", "续跑", "resume")):
        if not sector_id:
            return {
                "intent": "clarify",
                "clarify": "请先选择赛道",
                "assistant_message": "断点续跑需要先在右上角选择赛道。",
                "suggested_chips": [],
            }
        return {
            "intent": "run_agent",
            "agent_key": "orchestrator",
            "params": {"sector_id": sector_id, "resume": True, "stop_on_gate": True, "mode": "fusion"},
            "assistant_message": f"将从 Step {workflow_step or '?'} 断点续跑 Agent 流程，结果在右侧 GUI 确认。",
            "suggested_chips": ["查看待办", "扫描瓶颈"],
        }

    # 瓶颈（优先于泛化「扫描」赛道推荐）
    if any(k in low for k in ("瓶颈", "bottleneck", "卡脖子")):
        if not sector_id:
            return {
                "intent": "clarify",
                "clarify": "请先选择赛道",
                "assistant_message": "瓶颈扫描需要先选择赛道。",
                "suggested_chips": [],
            }
        return {
            "intent": "run_agent",
            "agent_key": "bottleneck_scout",
            "params": {"sector_id": sector_id},
            "assistant_message": "将扫描赛道内瓶颈环节，提案需在 GUI 确认。",
            "suggested_chips": ["Serenity 溯源", "候选融合"],
        }

    # Serenity
    if any(k in low for k in ("serenity", "溯源", "逆向", "小众")):
        if not sector_id:
            return {
                "intent": "clarify",
                "clarify": "请先选择赛道",
                "assistant_message": "Serenity 溯源需要先选择赛道。",
                "suggested_chips": [],
            }
        return {
            "intent": "run_agent",
            "agent_key": "serenity_path",
            "params": {"sector_id": sector_id},
            "assistant_message": "将运行 Serenity 逆向溯源 Agent。",
            "suggested_chips": ["扫描瓶颈", "生成报告"],
        }

    # 候选融合
    if any(k in low for k in ("融合", "候选", "fusion", "入池")):
        if not sector_id:
            return {
                "intent": "clarify",
                "clarify": "请先选择赛道",
                "assistant_message": "候选融合需要先选择赛道。",
                "suggested_chips": [],
            }
        return {
            "intent": "run_agent",
            "agent_key": "candidate_fusion",
            "params": {"sector_id": sector_id, "mode": "fusion"},
            "assistant_message": "将运行候选融合 Agent，入池须在候选池 GUI 人工确认。",
            "suggested_chips": ["扫描瓶颈", "生成报告"],
        }

    # 看空 / 反证
    if any(k in low for k in ("反证", "空头", "看空", "bear")):
        if not sector_id:
            return {
                "intent": "clarify",
                "clarify": "请先选择赛道",
                "assistant_message": "反证 Agent 需要先选择赛道。",
                "suggested_chips": [],
            }
        return {
            "intent": "run_agent",
            "agent_key": "bear_case",
            "params": {"sector_id": sector_id, "mode": "fusion"},
            "assistant_message": "将运行 BearCase 反证 Agent，高 severity 未回应将阻断入池。",
            "suggested_chips": ["候选融合", "生成报告"],
        }

    # 报告
    if any(k in low for k in ("报告", "graphrag", "看多", "论证")):
        if not sector_id:
            return {
                "intent": "clarify",
                "clarify": "请先选择赛道",
                "assistant_message": "报告生成需要先选择赛道。",
                "suggested_chips": [],
            }
        return {
            "intent": "run_agent",
            "agent_key": "report_graphrag",
            "params": {"sector_id": sector_id, "mode": "fusion"},
            "assistant_message": "将生成 GraphRAG 报告草稿，发布需人工审核。",
            "suggested_chips": ["空头对抗", "候选融合"],
        }

    # 监控
    if any(k in low for k in ("监控", "monitor", "保鲜", "告警")):
        return {
            "intent": "run_agent",
            "agent_key": "monitor_watch",
            "params": {"sector_id": sector_id, "mode": "fusion"} if sector_id else {"mode": "fusion"},
            "assistant_message": "将运行动态监控 Agent。",
            "suggested_chips": ["查看待办"],
        }

    # 知识抽取（需内容 — 引导去知识页）
    if any(k in low for k in ("知识", "抽取", "拓扑", "upload", "上传", "研报")):
        if not sector_id:
            return {
                "intent": "clarify",
                "assistant_message": "请先选择赛道；详细上传请在「知识抽取」页操作。",
                "suggested_chips": [],
            }
        if len(msg) >= 20:
            return {
                "intent": "run_agent",
                "agent_key": "knowledge_ingest",
                "params": {
                    "sector_id": sector_id,
                    "source_ref": "LUI对话",
                    "content": msg,
                },
                "assistant_message": "已从对话内容运行 Knowledge Agent，请在 GUI 校准确认草案。",
                "suggested_chips": ["扫描瓶颈"],
            }
        return {
            "intent": "navigate",
            "assistant_message": "知识抽取建议前往「知识抽取」页上传/粘贴研报（≥20字）；或在此直接粘贴段落文本。",
            "suggested_chips": ["扫描瓶颈", "同步成分股"],
            "params": {"route": "/knowledge"},
        }

    # 赛道推荐 / 冷启动（泛化意图放后）
    if any(
        k in low
        for k in (
            "扫描",
            "发现",
            "景气",
            "赛道",
            "冷启动",
            "推荐赛道",
            "sector",
        )
    ):
        force = any(k in low for k in ("冷启动", "全市场", "景气赛道", "发现景气"))
        params: dict[str, Any] = {"max_recommendations": 5}
        if focus and not force:
            params["focus"] = focus
        if force:
            params["force_cold_start"] = True
        m = re.search(r"关注(.{2,20})", msg)
        if m and "focus" not in params:
            params["focus"] = m.group(1).strip()
        return {
            "intent": "run_agent",
            "agent_key": "sector_recommend",
            "params": params,
            "assistant_message": "将运行赛道推荐 Agent，请在右侧 GUI 采纳推荐并确认景气。",
            "suggested_chips": ["从断点继续", "扫描瓶颈"],
        }

    return {
        "intent": "unknown",
        "assistant_message": (
            "暂未识别意图。可尝试：「发现景气赛道」「从断点继续」「扫描瓶颈」「候选融合」「生成报告」。"
        ),
        "suggested_chips": ["发现景气赛道", "从断点继续", "扫描瓶颈", "候选融合"],
    }


def resolve_intent(
    message: str,
    *,
    sector_id: str | None = None,
    focus: str | None = None,
    workflow_step: int | None = None,
    recent_messages: list[str] | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """P0 规则优先；unknown 时 P1 LLM 意图分类。"""
    result = parse_intent(
        message,
        sector_id=sector_id,
        focus=focus,
        workflow_step=workflow_step,
    )
    if result["intent"] != "unknown" or not use_llm:
        result["router"] = "rule"
        return result
    from app.services.intent_llm import classify_intent_llm

    llm = classify_intent_llm(
        message,
        sector_id=sector_id,
        focus=focus,
        workflow_step=workflow_step,
        recent_messages=recent_messages,
    )
    if llm:
        llm["router"] = "llm"
        return llm
    result["router"] = "rule"
    return result
