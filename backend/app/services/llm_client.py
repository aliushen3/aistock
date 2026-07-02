"""LLM 客户端 — DeepSeek/OpenAI 兼容 API，无 Key 时优雅降级。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_ENABLED, LLM_MODEL

logger = logging.getLogger(__name__)


def is_llm_enabled() -> bool:
    if LLM_ENABLED == "off":
        return False
    if LLM_ENABLED == "on":
        return bool(LLM_API_KEY)
    return bool(LLM_API_KEY)


def chat_completion(system: str, user: str, temperature: float = 0.3) -> str | None:
    if not is_llm_enabled():
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.warning("LLM 调用失败，降级为规则模板: %s", e)
        return None


def chat_with_tools(
    system: str,
    user: str,
    tools: list[dict],
    temperature: float = 0.2,
) -> dict | str | None:
    """OpenAI 兼容 function calling，返回 tool arguments dict。"""
    if not is_llm_enabled():
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=tools,
            tool_choice={"type": "function", "function": {"name": tools[0]["function"]["name"]}},
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            args = msg.tool_calls[0].function.arguments
            parsed = parse_json_response(args)
            return parsed if parsed else args
        if msg.content:
            return parse_json_response(msg.content) or msg.content
        return None
    except Exception as e:
        logger.warning("LLM tools 调用失败: %s", e)
        return None


def iterate_text_chunks(text: str, chunk_size: int = 4):
    """将文本切分为 SSE 流式片段。"""
    if not text:
        return
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]


def parse_json_response(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def enhance_report_with_llm(context: dict) -> dict | None:
    """GraphRAG Level-3 逻辑生成（LLM 接入点）。"""
    system = (
        "你是产业投研助手，不是投资顾问。\n"
        "- 仅基于提供的【图谱事实】和【文档摘录】推理\n"
        "- 每个论点 citations 数组必须引用 ref_id\n"
        "- 禁止预测股价、禁止买卖建议\n"
        "- 输出 JSON：{logic_chain:[{step,type,claim,citations,confidence}], "
        "counter_arguments:[{risk,severity,note}], summary:string}"
    )
    user = json.dumps(context, ensure_ascii=False, indent=2)
    raw = chat_completion(system, user, temperature=0.3)
    if not raw:
        return None
    return parse_json_response(raw)


def enhance_bearcase_with_llm(context: dict) -> dict | None:
    """BearCase 看空对抗（独立看空 prompt，主线一）。

    与看多 prompt 分离，要求以「证伪」为默认立场、强制 citation。
    """
    system = (
        "你是产业投研的【空头分析师】，职责是尽力证伪看多逻辑，不是投资顾问。\n"
        "- 仅基于提供的【规则看空基线】与【反面证据摘录】论证，每条 citations 必须引用 ref_id\n"
        "- 对每个标的逐项检查：技术替代/新增扩产/需求下滑/估值透支/政策风险/客户集中度/库存累积\n"
        "- 不确定时默认保留风险（severity 取保守值），禁止预测股价、禁止买卖建议\n"
        "- 输出 JSON：{bear_cases:[{stock_code,dimension,risk,severity,probability,"
        "what_would_confirm,citations}]}"
    )
    user = json.dumps(context, ensure_ascii=False, indent=2)
    raw = chat_completion(system, user, temperature=0.3)
    if not raw:
        return None
    return parse_json_response(raw)
