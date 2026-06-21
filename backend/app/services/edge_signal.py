"""预期差信号（入池闸一）— 度量市场一致预期已 price in 的程度。

确定性规则，非投资决策；数据缺失显式降级（degraded=true），禁止 LLM 猜测填充。
对齐 docs/DESIGN.md §6.3 / §2.6 闸一。
"""

from __future__ import annotations

from app.services.graph_store import get_store


def _crowding_level(pe: float | None, turnover: float | None) -> str:
    """由估值分位 + 成交额分位综合判断拥挤/透支程度。"""
    if pe is None and turnover is None:
        return "unknown"
    pe = pe if pe is not None else 0.0
    turnover = turnover if turnover is not None else 0.0
    if pe >= 0.8 and turnover >= 0.7:
        return "high"
    if pe >= 0.6 or turnover >= 0.5:
        return "medium"
    return "low"


def compute_edge_signal(stock_code: str) -> dict:
    """返回预期差评估卡。priced_in: low|medium|high|unknown。

    信号（一期以行情/估值分位近似一致预期，ods_consensus 留待 F9）：
    - pe_percentile：估值历史分位（高 = 预期已反映）
    - turnover_percentile：成交额分位（高 = 拥挤）
    - analyst_coverage：机构覆盖（高 = 认知充分、认知差小）
    """
    company = get_store().get_company(stock_code)
    if company is None:
        return {
            "priced_in": "unknown",
            "degraded": True,
            "reason": "无公司行情/估值数据，无法评估 price-in",
            "evidence_refs": [],
        }

    pe = company.get("pe_percentile")
    turnover = company.get("turnover_percentile")
    coverage = company.get("analyst_coverage")

    priced_in = _crowding_level(pe, turnover)
    # 机构覆盖高进一步推高 price-in（认知差小）
    if priced_in == "medium" and coverage is not None and coverage >= 30:
        priced_in = "high"

    degraded = pe is None and turnover is None
    return {
        "priced_in": priced_in,
        "crowding_percentile": turnover,
        "pe_percentile": pe,
        "rating_dispersion": None,  # 留待 ods_consensus（F9）
        "eps_revision_trend": "unknown",  # 留待 ods_consensus（F9）
        "analyst_coverage": coverage,
        "degraded": degraded,
        "flag": "预期透支" if priced_in == "high" else None,
        "evidence_refs": [],
        "disclaimer": "预期差为辅助提示，不构成投资建议",
    }
