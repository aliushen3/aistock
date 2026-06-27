"""知识抽取 Agent 工具集。"""

from __future__ import annotations

from typing import Any

from app.services import extraction as extraction_service
from app.services.document_store import list_documents
from app.services.graph_store import get_store
from app.services.vector_store import search_documents

TOOL_SPECS: list[dict] = [
    {
        "name": "list_products",
        "description": "列出赛道内已知产品节点（用于关系对齐）",
        "input_schema": {"sector_id": "赛道 ID"},
    },
    {
        "name": "list_uploaded_documents",
        "description": "列出已上传研报元数据",
        "input_schema": {"sector_id": "赛道 ID"},
    },
    {
        "name": "search_research_evidence",
        "description": "检索上传研报片段作为证据",
        "input_schema": {"query": "检索词", "sector_id": "赛道 ID"},
    },
    {
        "name": "rule_extract_preview",
        "description": "规则抽取预览（不落库）",
        "input_schema": {"sector_id": "赛道 ID", "content": "文本"},
    },
    {
        "name": "llm_extract_preview",
        "description": "LLM 抽取预览（不落库，无 Key 时返回空）",
        "input_schema": {"sector_id": "赛道 ID", "content": "文本"},
    },
]


def tool_list_products(sector_id: str) -> list[dict]:
    store = get_store()
    return [
        {"id": p["id"], "name": p["name"], "bottleneck_status": p.get("bottleneck_status")}
        for p in store.list_products(sector_id)
    ]


def tool_list_uploaded_documents(sector_id: str) -> list[dict]:
    return list_documents(sector_id)


def tool_search_research_evidence(query: str, sector_id: str, top_k: int = 5) -> list[dict]:
    return search_documents(query, sector_id=sector_id, top_k=top_k)


def tool_rule_extract_preview(sector_id: str, content: str) -> dict:
    return extraction_service.extract_from_text(content, sector_id)


def tool_llm_extract_preview(sector_id: str, content: str) -> dict:
    result = extraction_service.extract_with_llm(content, sector_id)
    return result or {"relations": [], "bottleneck_hints": [], "new_products": [], "extractor": "llm_unavailable"}


def execute_tool(name: str, action_input: dict | None = None) -> Any:
    inp = action_input or {}
    if name == "list_products":
        return tool_list_products(inp["sector_id"])
    if name == "list_uploaded_documents":
        return tool_list_uploaded_documents(inp["sector_id"])
    if name == "search_research_evidence":
        return tool_search_research_evidence(inp.get("query", "产业链 上游"), inp["sector_id"])
    if name == "rule_extract_preview":
        return tool_rule_extract_preview(inp["sector_id"], inp["content"])
    if name == "llm_extract_preview":
        return tool_llm_extract_preview(inp["sector_id"], inp["content"])
    raise ValueError(f"未知工具: {name}")
