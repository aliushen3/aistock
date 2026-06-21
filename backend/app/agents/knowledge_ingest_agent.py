"""知识抽取智能体 — ReAct 工具调用 + 规则/LLM 抽取 → 知识草案。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.agents.knowledge_agent_tools import TOOL_SPECS, execute_tool, tool_rule_extract_preview
from app.services import extraction as extraction_service
from app.services.graph_store import get_store
from app.services.llm_client import chat_completion, is_llm_enabled, parse_json_response

REACT_SYSTEM = """你是 AiStock 知识抽取智能体（ReAct 模式）。

## 可用工具
""" + json.dumps(TOOL_SPECS, ensure_ascii=False) + """

## 工作方式
每轮输出 JSON（不要 markdown）：
- 需要更多信息：{"thought":"...","action":"工具名","action_input":{...}}
- 完成抽取：{"thought":"...","final_answer":{...}}

final_answer 格式：
{
  "agent_summary": "一句话总结",
  "extracted": {
    "relations": [{"type":"UPSTREAM_OF","source_name":"","target_name":"","confidence":"medium"}],
    "bottleneck_hints": [{"product_name":"","confidence":"low"}],
    "evidence_excerpt": ""
  }
}

优先调用 list_products 对齐产品名，再用 rule_extract_preview 或 llm_extract_preview。"""

FINAL_SYSTEM = """你是知识抽取智能体。基于工具结果输出 final_answer JSON，格式同上。"""

MAX_REACT_STEPS = 4


def _normalize_extracted(raw: dict, sector_id: str) -> dict:
    """将 LLM 输出的名称对齐为 product_id。"""
    store = get_store()
    name_to_id = {p["name"]: p["id"] for p in store.list_products(sector_id)}
    relations = []
    for rel in raw.get("relations", []):
        if rel.get("source_id") and rel.get("target_id"):
            relations.append(rel)
            continue
        up_id = name_to_id.get(rel.get("source_name", ""))
        down_id = name_to_id.get(rel.get("target_name", ""))
        if up_id and down_id:
            relations.append(
                {
                    "type": "UPSTREAM_OF",
                    "source_id": up_id,
                    "source_name": rel.get("source_name"),
                    "target_id": down_id,
                    "target_name": rel.get("target_name"),
                    "confidence": rel.get("confidence", "medium"),
                }
            )
    hints = []
    for hint in raw.get("bottleneck_hints", []):
        if hint.get("product_id"):
            hints.append(hint)
            continue
        pid = name_to_id.get(hint.get("product_name", ""))
        if pid:
            hints.append(
                {
                    "type": "bottleneck_hint",
                    "product_id": pid,
                    "product_name": hint.get("product_name"),
                    "confidence": hint.get("confidence", "low"),
                }
            )
    return {
        "relations": relations,
        "bottleneck_hints": hints,
        "evidence_excerpt": raw.get("evidence_excerpt", ""),
        "extractor": raw.get("extractor", "agent_v1"),
    }


def _rule_extract(sector_id: str, content: str, source_ref: str) -> dict:
    extracted = tool_rule_extract_preview(sector_id, content)
    return {
        "agent_summary": f"规则抽取完成：{len(extracted.get('relations', []))} 条关系，"
        f"{len(extracted.get('bottleneck_hints', []))} 条瓶颈提示",
        "extracted": extracted,
        "agent_mode": "rule_v1",
    }


def _react_loop(sector_id: str, content: str, source_ref: str) -> tuple[dict | None, list[dict]]:
    tool_results: list[dict] = []
    context = (
        f"赛道: {sector_id}\n来源: {source_ref}\n"
        f"待抽取文本（前 2000 字）:\n{content[:2000]}\n"
        f"请调用工具完成抽取。"
    )
    bound_input = {"sector_id": sector_id, "content": content}

    for step in range(MAX_REACT_STEPS):
        prior = json.dumps(tool_results, ensure_ascii=False, indent=2) if tool_results else "（尚无）"
        user = f"{context}\n\n工具结果:\n{prior}\n\n第 {step + 1} 轮，请输出 JSON。"
        raw = chat_completion(REACT_SYSTEM, user, temperature=0.2)
        if not raw:
            return None, tool_results
        parsed = parse_json_response(raw)
        if not parsed:
            continue

        if parsed.get("final_answer"):
            answer = parsed["final_answer"]
            extracted = _normalize_extracted(answer.get("extracted", {}), sector_id)
            return (
                {
                    "agent_summary": answer.get("agent_summary", "知识抽取完成"),
                    "extracted": extracted,
                    "agent_mode": "react_llm_v1",
                    "react_steps": step + 1,
                },
                tool_results,
            )

        action = parsed.get("action")
        if not action:
            continue
        inp = {**bound_input, **(parsed.get("action_input") or {})}
        try:
            observation = execute_tool(action, inp)
            tool_results.append(
                {
                    "step": step + 1,
                    "thought": parsed.get("thought"),
                    "action": action,
                    "observation": observation,
                }
            )
        except Exception as e:
            tool_results.append({"step": step + 1, "action": action, "error": str(e)})

    user = f"{context}\n\n工具结果:\n{json.dumps(tool_results, ensure_ascii=False)}\n请输出 final_answer。"
    raw = chat_completion(FINAL_SYSTEM, user, temperature=0.2)
    if not raw:
        return None, tool_results
    parsed = parse_json_response(raw)
    if parsed and parsed.get("extracted"):
        extracted = _normalize_extracted(parsed["extracted"], sector_id)
        return (
            {
                "agent_summary": parsed.get("agent_summary", "知识抽取完成"),
                "extracted": extracted,
                "agent_mode": "react_llm_v1",
                "react_steps": MAX_REACT_STEPS,
            },
            tool_results,
        )
    return None, tool_results


def run_knowledge_ingest_agent(
    sector_id: str,
    source_type: str,
    source_ref: str,
    content: str,
    operator: str = "analyst",
) -> dict:
    if get_store().get_sector(sector_id) is None:
        raise ValueError(f"赛道不存在: {sector_id}")
    if len(content.strip()) < 20:
        raise ValueError("文本过短，无法抽取")

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    react_trace: list[dict] = []
    result: dict | None = None

    if is_llm_enabled():
        result, react_trace = _react_loop(sector_id, content, source_ref)
    if result is None:
        result = _rule_extract(sector_id, content, source_ref)

    draft = extraction_service.ingest_document(
        sector_id,
        source_type,
        source_ref,
        content,
        operator=operator,
        extracted=result["extracted"],
        agent_mode=result.get("agent_mode", "rule_v1"),
    )

    return {
        "run_id": run_id,
        "agent": "knowledge_ingest_react_v1",
        "agent_mode": result.get("agent_mode", "rule_v1"),
        "llm_enabled": is_llm_enabled(),
        "react_steps": result.get("react_steps", len(react_trace)),
        "react_trace": react_trace,
        "agent_summary": result.get("agent_summary", ""),
        "draft_id": draft["draft_id"],
        "extracted": draft["extracted"],
        "status": draft["status"],
        "message": "草案已生成，须经 CalibrateChain / confirm 后生效",
    }
