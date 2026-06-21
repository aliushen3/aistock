"""价值捕获研判（入池闸二）— 瓶颈环节能否把稀缺转化为利润。

确定性规则，非投资决策；数据缺失显式降级。对齐 docs/DESIGN.md §6.3 / §2.6 闸二。
"""

from __future__ import annotations

from app.ontology.property_overlays import merge_product
from app.services.graph_store import get_store


def _pricing_mechanism(product: dict | None) -> str:
    """长协锁价(无弹性) vs 市场定价(有弹性)。

    一期近似：海外高依赖 + 认证周期长的环节多为长协/客户锁定；否则市场定价。
    """
    if product is None:
        return "unknown"
    if product.get("overseas_dependence") == "high" and product.get("certification_months", 0) >= 18:
        return "contract"
    return "market"


def compute_value_capture(product_id: str, company_code: str) -> dict:
    """返回价值捕获卡。captures_economics: yes|partial|no|unknown。

    信号：
    - gross_margin：议价权（高毛利 = 利润留存能力强）
    - market_rank：环节地位（龙头议价权强）
    - pricing_mechanism：定价机制（长协锁价削弱涨价弹性）
    """
    store = get_store()
    company = store.get_company(company_code)
    product = merge_product(store.get_product(product_id), product_id) if product_id else None

    if company is None:
        return {
            "captures_economics": "unknown",
            "degraded": True,
            "reason": "无公司财务数据，无法评估价值捕获",
            "evidence_refs": [],
        }

    gross_margin = company.get("gross_margin")
    market_rank = company.get("market_rank")
    pricing = _pricing_mechanism(product)

    if gross_margin is None:
        captures = "unknown"
        degraded = True
    else:
        degraded = False
        # 高毛利 + 龙头/前列 + 非长协锁价 → 能捕获
        strong_margin = gross_margin >= 0.35
        strong_rank = market_rank is not None and market_rank <= 3
        if strong_margin and (strong_rank or pricing == "market"):
            captures = "yes"
        elif strong_margin or strong_rank:
            captures = "partial"
        else:
            captures = "no"
        # 长协锁价削弱涨价弹性：yes 降为 partial
        if captures == "yes" and pricing == "contract":
            captures = "partial"

    return {
        "captures_economics": captures,
        "gross_margin": gross_margin,
        "gross_margin_trend": "unknown",  # 趋势需时序数据，留待后续
        "market_rank": market_rank,
        "customer_concentration": None,  # 需财报前五大客户，留待后续
        "pricing_mechanism": pricing,
        "degraded": degraded,
        "flag": "利润不在此环节" if captures in ("no", "partial") else None,
        "evidence_refs": [],
        "disclaimer": "价值捕获为辅助提示，不构成投资建议",
    }
