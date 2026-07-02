"""LLM 意图分类 — function calling，规则 unknown 时兜底。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.llm_client import chat_with_tools, is_llm_enabled, parse_json_response

logger = logging.getLogger(__name__)

AGENT_KEYS = [
    "sector_recommend",
    "orchestrator",
    "bottleneck_scout",
    "serenity_path",
    "candidate_fusion",
    "report_graphrag",
    "monitor_watch",
    "knowledge_ingest",
    "bear_case",
]

INTENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "dispatch_agent_intent",
            "description": "将用户投研自然语言路由到 Agent 动作或导航",
            "parameters": {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": ["run_agent", "navigate", "clarify"],
                    },
                    "agent_key": {
                        "type": "string",
                        "enum": AGENT_KEYS,
                        "description": "intent=run_agent 时必填",
                    },
                    "params": {"type": "object", "description": "Agent 参数 JSON"},
                    "assistant_message": {"type": "string", "description": "回复用户的简短说明"},
                    "suggested_chips": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "route": {"type": "string", "description": "intent=navigate 时的前端路径"},
                    "clarify": {"type": "string", "description": "intent=clarify 时的追问"},
                },
                "required": ["intent", "assistant_message", "suggested_chips"],
            },
        },
    }
]

SYSTEM = """你是 AiStock 投研 Agent 的意图路由器。根据用户消息与上下文，调用 dispatch_agent_intent。
规则：
- 发现/扫描景气赛道 → sector_recommend（force 冷启动时 params 含 force_cold_start:true）
- 断点续跑/继续 → orchestrator（params: resume:true, stop_on_gate:true, mode:fusion, sector_id）
- 瓶颈/卡脖子 → bottleneck_scout
- Serenity/溯源/逆向 → serenity_path
- 候选融合/入池 → candidate_fusion
- 报告/GraphRAG/看多 → report_graphrag
- 反证/空头/看空 → bear_case
- 监控/告警 → monitor_watch
- 上传/抽取知识（≥20字内容）→ knowledge_ingest（params 含 content）
- 短知识指令无内容 → navigate /knowledge
- 缺 sector_id 且需要赛道 → clarify
禁止预测股价；assistant_message 用中文，简洁。"""


def _build_user_payload(
    message: str,
    *,
    sector_id: str | None,
    focus: str | None,
    workflow_step: int | None,
    recent_messages: list[str] | None,
) -> str:
    ctx = {
        "message": message,
        "sector_id": sector_id,
        "focus": focus,
        "workflow_step": workflow_step,
        "recent_messages": (recent_messages or [])[-6:],
    }
    return json.dumps(ctx, ensure_ascii=False)


def _normalize_llm_intent(raw: dict[str, Any]) -> dict[str, Any]:
    intent = raw.get("intent", "unknown")
    if intent not in ("run_agent", "navigate", "clarify"):
        return {
            "intent": "unknown",
            "assistant_message": raw.get("assistant_message", "暂未识别意图"),
            "suggested_chips": raw.get("suggested_chips") or [],
        }

    out: dict[str, Any] = {
        "intent": intent,
        "assistant_message": raw.get("assistant_message") or "",
        "suggested_chips": raw.get("suggested_chips") or [],
    }
    if intent == "clarify":
        out["clarify"] = raw.get("clarify") or raw.get("assistant_message")
        return out
    if intent == "navigate":
        route = raw.get("route") or (raw.get("params") or {}).get("route") or "/"
        out["params"] = {"route": route}
        return out

    agent_key = raw.get("agent_key")
    if agent_key not in AGENT_KEYS:
        return {
            "intent": "unknown",
            "assistant_message": "LLM 返回了无效 Agent，请换种说法。",
            "suggested_chips": ["发现景气赛道", "从断点继续", "扫描瓶颈"],
        }
    params = dict(raw.get("params") or {})
    if params.get("sector_id") is None and raw.get("sector_id"):
        params["sector_id"] = raw["sector_id"]
    out["agent_key"] = agent_key
    out["params"] = params
    if raw.get("clarify"):
        out["clarify"] = raw["clarify"]
    return out


def classify_intent_llm(
    message: str,
    *,
    sector_id: str | None = None,
    focus: str | None = None,
    workflow_step: int | None = None,
    recent_messages: list[str] | None = None,
) -> dict[str, Any] | None:
    if not is_llm_enabled():
        return None
    user = _build_user_payload(
        message,
        sector_id=sector_id,
        focus=focus,
        workflow_step=workflow_step,
        recent_messages=recent_messages,
    )
    try:
        tool_args = chat_with_tools(SYSTEM, user, INTENT_TOOLS, temperature=0.1)
        if not tool_args:
            return None
        if isinstance(tool_args, str):
            parsed = parse_json_response(tool_args)
        else:
            parsed = tool_args
        if not parsed:
            return None
        result = _normalize_llm_intent(parsed)
        if sector_id and result.get("intent") == "run_agent":
            params = result.setdefault("params", {})
            if "sector_id" not in params and result.get("agent_key") not in ("sector_recommend", "monitor_watch"):
                params["sector_id"] = sector_id
        if focus and result.get("agent_key") == "sector_recommend":
            params = result.setdefault("params", {})
            params.setdefault("focus", focus)
        if workflow_step and result.get("agent_key") == "orchestrator":
            params = result.setdefault("params", {})
            params.setdefault("resume", True)
        return result
    except Exception as e:
        logger.warning("LLM 意图分类失败: %s", e)
        return None
