"""赛道推荐智能体 — ReAct 多轮工具调用 + LLM/规则推理。

流程：
1. ReAct 循环（LLM）：按需调用工具采集证据、抽取研报主题
2. 综合推荐：输出结构化 beta_candidate 提案
3. 落库 + 触发 Object Set 告警
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.agents.sector_agent_tools import (
    TOOL_SPECS,
    build_agent_context,
    execute_tool,
    tool_get_watchlist,
)
from app.services.llm_client import chat_completion, is_llm_enabled, parse_json_response
from app.services.object_set_alerts import push_sector_recommendation_alerts
from app.services.sector_recommendations import save_recommendations

REACT_SYSTEM = """你是 AiStock 赛道研判智能体（ReAct 模式）。

## 可用工具
""" + json.dumps(TOOL_SPECS, ensure_ascii=False) + """

## 工作方式
每轮必须输出一个 JSON（不要 markdown）：
- 需要更多信息：{"thought":"推理","action":"工具名","action_input":{...}}
- 信息足够：{"thought":"总结","final_answer":{...}}

final_answer 格式：
{
  "agent_summary": "一句话总结",
  "recommendations": [{
    "sector_name": "", "sector_id": null或已有ID, "is_new": true/false,
    "beta_score": 0.0-1.0, "demand_growth_hint": 数字,
    "signals": {"demand_growth_ok":bool,"capex_positive":bool,"research_support_count":0},
    "rationale": "", "terminal_products": [],
    "evidence_refs": [{"ref_id":"","excerpt":""}],
    "risks": [], "next_actions": []
  }]
}

## 判定标准
需求增速>20%、资本开支为正、有研报证据。禁止股价预测。
建议至少调用 extract_sector_themes_from_reports 与 search_research_evidence。"""

FINAL_SYSTEM = """你是 AiStock 赛道研判智能体。基于已采集的工具结果输出最终 JSON 推荐。
格式同 final_answer，禁止 markdown。"""

MAX_REACT_STEPS = 5


def _slug_sector_id(name: str) -> str:
    ascii_part = re.sub(r"[^a-zA-Z0-9]", "", name.lower())[:16]
    if ascii_part:
        return f"sector_{ascii_part}"
    return f"sector_{uuid.uuid4().hex[:8]}"


def _count_keyword_hits(text: str, keywords: list[str]) -> int:
    return sum(1 for k in keywords if k in text)


def _rule_recommend(context: dict, max_items: int = 5) -> dict:
    existing = {s["id"]: s for s in context["existing_sectors"]}
    metrics_by_id = {m["sector_id"]: m for m in context["metrics_signals"]}
    evidence_text = " ".join(
        f"{h.get('source_ref', '')} {h.get('excerpt', '')}" for h in context["evidence_hits"]
    )
    criteria = context["beta_criteria"]
    recs: list[dict] = []

    for watch in context.get("watchlist", tool_get_watchlist()):
        sid = watch.get("sector_id")
        sector_row = existing.get(sid) if sid else None
        metrics = metrics_by_id.get(sid) if sid else None
        keywords = watch.get("keywords", [watch["sector_name"]])
        kw_hits = _count_keyword_hits(evidence_text, keywords)
        theme_refs = watch.get("evidence_refs", [])
        if theme_refs:
            kw_hits = max(kw_hits, len(theme_refs))

        demand = metrics.get("sector_demand_growth") if metrics else None
        capex = metrics.get("sector_capex_yoy") if metrics else None

        score = 0.3
        if watch.get("source") in ("report", "report_llm", "report_rule"):
            score += 0.15
        signals: dict[str, Any] = {
            "demand_growth_ok": False,
            "capex_positive": False,
            "research_support_count": kw_hits,
        }
        if demand is not None and demand >= criteria["demand_growth_threshold"]:
            score += 0.25
            signals["demand_growth_ok"] = True
        if capex is not None and capex > 0:
            score += 0.15
            signals["capex_positive"] = True
        if kw_hits > 0:
            score += min(0.25, kw_hits * 0.08)
        if metrics and metrics.get("high_utilization_products"):
            score += 0.1
        if sector_row and sector_row.get("status") == "beta_candidate":
            score += 0.05

        if score < 0.4 and kw_hits == 0 and not theme_refs:
            continue

        evidence_refs = theme_refs[:3] if theme_refs else [
            {"ref_id": h.get("ref_id"), "excerpt": (h.get("excerpt") or "")[:120]}
            for h in context["evidence_hits"]
            if any(k in f"{h.get('source_ref', '')} {h.get('excerpt', '')}" for k in keywords)
        ][:3]

        recs.append(
            {
                "sector_name": watch["sector_name"],
                "sector_id": sid,
                "is_new": sid is None,
                "beta_score": round(min(score, 0.99), 2),
                "demand_growth_hint": round(demand * 100, 1) if demand is not None else None,
                "signals": signals,
                "rationale": _build_rationale(watch, metrics, signals, sector_row),
                "terminal_products": watch.get("terminal_products", []),
                "evidence_refs": evidence_refs,
                "risks": _default_risks(watch["sector_name"]),
                "next_actions": _next_actions(sid, sector_row),
            }
        )

    recs.sort(key=lambda x: -x["beta_score"])

    cold_start_used = False
    if not recs:
        cold_recs = _cold_start_recommendations(context, max_items)
        if cold_recs:
            recs = cold_recs
            cold_start_used = True

    theme_count = len(context.get("report_themes", {}).get("themes", []))
    summary = (
        f"规则扫描：研报抽取 {theme_count} 个主题，"
        f"证据 {len(context['evidence_hits'])} 条，推荐 {len(recs[:max_items])} 个赛道"
    )
    if cold_start_used:
        summary = (
            f"冷启动扫描：无存量赛道/研报证据，基于东财行业轮动与同花顺热点"
            f"生成 {len(recs[:max_items])} 个待验证候选赛道"
        )
    return {
        "agent_summary": summary,
        "recommendations": recs[:max_items],
        "agent_mode": "cold_start_v1" if cold_start_used else "rule_v1",
    }


def _cold_start_recommendations(context: dict, max_items: int) -> list[dict]:
    """空图冷启动：用行业轮动排名 + 热点题材生成待验证候选赛道。"""
    cold = context.get("cold_start_signals") or {}
    ranking = cold.get("industry_ranking") or []
    hot_themes = cold.get("hot_themes") or []
    theme_text = "、".join(
        f"{t.get('name')}（{t.get('reason')}）" for t in hot_themes[:3] if t.get("name")
    )

    recs: list[dict] = []
    seen: set[str] = set()
    for row in ranking[:max_items]:
        name = (row.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        change_pct = row.get("change_pct")
        leader = row.get("leader") or ""
        rationale = (
            f"冷启动候选：东财行业板块「{name}」近日涨幅 {change_pct}%"
            + (f"，领涨 {leader}" if leader else "")
            + (f"；当日热点：{theme_text}" if theme_text else "")
            + "。无存量证据，须研究员补全产业链拓扑后再确认。"
        )
        recs.append(
            {
                "sector_name": name,
                "sector_id": None,
                "is_new": True,
                "beta_score": 0.35,
                "demand_growth_hint": None,
                "signals": {
                    "demand_growth_ok": False,
                    "capex_positive": False,
                    "research_support_count": 0,
                },
                "rationale": rationale,
                "terminal_products": [],
                "evidence_refs": [],
                "risks": _default_risks(name),
                "next_actions": ["采纳后补全产业链拓扑", "上传研报补强证据", "同步成分股与行情"],
            }
        )
    return recs


def _build_rationale(watch: dict, metrics: dict | None, signals: dict, sector_row: dict | None) -> str:
    parts = [f"「{watch['sector_name']}」"]
    if watch.get("source", "").startswith("report"):
        parts.append("研报主题抽取命中")
    if metrics:
        d, c = metrics.get("sector_demand_growth"), metrics.get("sector_capex_yoy")
        if d is not None:
            parts.append(f"需求增速提示 {d*100:.0f}%")
        if c is not None:
            parts.append(f"资本开支同比 {c*100:.0f}%")
        if metrics.get("high_utilization_products"):
            names = [p["product_name"] for p in metrics["high_utilization_products"][:2]]
            parts.append(f"{'/'.join(names)} 产能利用率高")
    if signals.get("research_support_count", 0) > 0:
        parts.append(f"证据支撑 {signals['research_support_count']} 处")
    if sector_row and not sector_row.get("human_confirmed"):
        parts.append("系统内待确认")
    return "；".join(parts) + "。"


def _default_risks(name: str) -> list[str]:
    return [
        "景气度可能已部分 priced in",
        "扩产周期后供需或反转",
        f"「{name}」产业链图谱可能尚未完整，需专家补全",
    ]


def _next_actions(sector_id: str | None, sector_row: dict | None) -> list[str]:
    if sector_id and sector_row:
        if sector_row.get("status") != "beta_confirmed":
            return ["ConfirmSectorBeta", "查看产业图谱", "上传深度研报"]
        return ["查看候选池", "生成 GraphRAG 报告"]
    return ["采纳赛道提案", "专家构建产业链拓扑", "上传研报补强证据"]


def _react_loop(focus: str | None, query: str | None, max_items: int) -> tuple[dict | None, list[dict]]:
    """多轮 ReAct：LLM 选择工具 → 执行 → 再推理。"""
    tool_results: list[dict] = []
    messages_context = (
        f"研究员关注: {focus or '开放式扫描'}\n"
        f"补充问题: {query or '无'}\n"
        f"最多推荐 {max_items} 个赛道。请开始调用工具。"
    )

    for step in range(MAX_REACT_STEPS):
        prior = json.dumps(tool_results, ensure_ascii=False, indent=2) if tool_results else "（尚无工具结果）"
        user = f"{messages_context}\n\n已执行工具结果:\n{prior}\n\n第 {step + 1} 轮，请输出 JSON。"
        raw = chat_completion(REACT_SYSTEM, user, temperature=0.2)
        if not raw:
            return None, tool_results

        parsed = parse_json_response(raw)
        if not parsed:
            continue

        if parsed.get("final_answer"):
            answer = parsed["final_answer"]
            answer["agent_mode"] = "react_llm_v1"
            answer["react_steps"] = step + 1
            if answer.get("recommendations"):
                answer["recommendations"] = answer["recommendations"][:max_items]
            return answer, tool_results + [{"step": step + 1, "type": "final", "thought": parsed.get("thought")}]

        action = parsed.get("action")
        if not action:
            continue
        try:
            observation = execute_tool(action, parsed.get("action_input") or {})
            tool_results.append(
                {
                    "step": step + 1,
                    "thought": parsed.get("thought"),
                    "action": action,
                    "action_input": parsed.get("action_input"),
                    "observation": observation,
                }
            )
        except Exception as e:
            tool_results.append({"step": step + 1, "action": action, "error": str(e)})

    # 达最大步数：用工具结果做最终汇总
    user = (
        f"关注: {focus or '开放式扫描'}\n"
        f"工具结果:\n{json.dumps(tool_results, ensure_ascii=False, indent=2)}\n"
        f"请输出 final_answer JSON，最多 {max_items} 个推荐。"
    )
    raw = chat_completion(FINAL_SYSTEM, user, temperature=0.2)
    if not raw:
        return None, tool_results
    parsed = parse_json_response(raw)
    if parsed and parsed.get("recommendations"):
        parsed["agent_mode"] = "react_llm_v1"
        parsed["react_steps"] = MAX_REACT_STEPS
        parsed["recommendations"] = parsed["recommendations"][:max_items]
        return parsed, tool_results
    return None, tool_results


def _llm_recommend(context: dict, max_items: int = 5) -> dict | None:
    """单次 LLM 推荐（ReAct 失败时的 fallback）。"""
    user = (
        f"研究员关注方向: {context.get('focus') or '开放式扫描'}\n"
        f"补充说明: {context.get('query') or '无'}\n"
        f"最多推荐 {max_items} 个赛道。\n\n"
        f"上下文数据:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    raw = chat_completion(FINAL_SYSTEM, user, temperature=0.2)
    if not raw:
        return None
    parsed = parse_json_response(raw)
    if not parsed or not parsed.get("recommendations"):
        return None
    parsed["agent_mode"] = "llm_v1"
    parsed["recommendations"] = parsed["recommendations"][:max_items]
    return parsed


def _llm_enhance_summary(context: dict, result: dict) -> dict | None:
    """B 类 Pipeline：LLM 仅增强摘要与措辞，不驱动 ReAct 扫描。"""
    user = (
        f"关注: {context.get('focus') or '开放式扫描'}\n"
        f"规则扫描结果:\n{json.dumps(result.get('recommendations', [])[:3], ensure_ascii=False)}\n"
        "请输出 JSON：{\"agent_summary\":\"一句话总结\"}，禁止 markdown。"
    )
    raw = chat_completion(
        "你是赛道研判助手。仅润色摘要，不改变推荐列表与分数。",
        user,
        temperature=0.2,
    )
    if not raw:
        return None
    parsed = parse_json_response(raw)
    if not parsed or not parsed.get("agent_summary"):
        return None
    enhanced = dict(result)
    enhanced["agent_summary"] = parsed["agent_summary"]
    return enhanced


def run_sector_recommend_agent(
    focus: str | None = None,
    query: str | None = None,
    max_recommendations: int = 5,
    operator: str = "analyst",
) -> dict:
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    context = build_agent_context(focus=focus, query=query)

    result = _rule_recommend(context, max_items=max_recommendations)
    result["agent_mode"] = "pipeline_rule_v1"
    llm_assisted = False

    if is_llm_enabled():
        enhanced = _llm_enhance_summary(context, result)
        if enhanced:
            result = enhanced
            result["agent_mode"] = "pipeline_llm_assist_v1"
            llm_assisted = True

    saved = save_recommendations(
        run_id=run_id,
        items=result["recommendations"],
        focus=focus,
        agent_mode=result.get("agent_mode", "pipeline_rule_v1"),
        operator=operator,
    )

    alert_items = push_sector_recommendation_alerts(saved, run_id)

    return {
        "run_id": run_id,
        "agent": "sector_recommend_pipeline_v1",
        "agent_mode": result.get("agent_mode", "pipeline_rule_v1"),
        "llm_enabled": is_llm_enabled(),
        "llm_assisted": llm_assisted,
        "agent_summary": result.get("agent_summary", ""),
        "context_stats": {
            "existing_sectors": len(context["existing_sectors"]),
            "metrics_signals": len(context["metrics_signals"]),
            "evidence_hits": len(context["evidence_hits"]),
            "report_themes": len(context.get("report_themes", {}).get("themes", [])),
            "watchlist_count": context.get("watchlist_meta", {}).get(
                "watchlist_count", len(context.get("watchlist", []))
            ),
            "watchlist_sources": context.get("watchlist_meta", {}).get("source_counts", {}),
        },
        "recommendations": saved,
        "alerts_pushed": alert_items,
        "disclaimer": "推荐结果仅供投研参考，须经研究员 ConfirmSectorBeta 确认后方可进入后续流程",
    }


def make_sector_id_for_adopt(sector_name: str, existing_id: str | None) -> str:
    if existing_id:
        return existing_id
    return _slug_sector_id(sector_name)
