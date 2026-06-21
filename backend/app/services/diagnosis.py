"""散户 vs 专业模式智能诊断（DESIGN §8 模块 3）。"""

from __future__ import annotations

from app.ontology.property_overlays import merge_product
from app.services.graph_store import InMemoryGraphStore
from app.services.hint_score import calc_bottleneck_hint


def diagnose_company(store: InMemoryGraphStore, sector_id: str, stock_code: str) -> dict:
    company = store.get_company(stock_code)
    if company is None:
        raise ValueError(f"公司不存在: {stock_code}")

    retail_score = 0.0
    pro_score = 0.0
    signals: list[dict] = []

    # 散户陷阱信号
    if (company.get("turnover_percentile") or 0) >= 0.7:
        retail_score += 25
        signals.append({"type": "retail", "signal": "高换手拥挤", "detail": "成交额分位偏高，题材炒作风险"})
    if (company.get("pe_percentile") or 0) >= 0.75:
        retail_score += 20
        signals.append({"type": "retail", "signal": "估值透支", "detail": "PE 历史分位偏高"})
    if (company.get("analyst_coverage") or 0) >= 20:
        retail_score += 10
        signals.append({"type": "retail", "signal": "高机构覆盖", "detail": "认知差有限，追涨风险"})

    # 专业 Alpha 信号
    produces = company.get("produces", [])
    bottleneck_products = []
    niche_products = []
    for pid in produces:
        p = merge_product(store.get_product(pid), pid)
        if not p or p.get("sector_id") != sector_id:
            continue
        if p.get("bottleneck_status") == "bottleneck_confirmed":
            pro_score += 30
            bottleneck_products.append(p["name"])
        elif p.get("bottleneck_status") == "bottleneck_hint":
            pro_score += 15
            bottleneck_products.append(p["name"])
        if p.get("serenity_niche_confirmed") or (
            p.get("serenity_niche") and p.get("serenity_niche_confirmed", False)
        ):
            pro_score += 20
            niche_products.append(p["name"])
        hint = calc_bottleneck_hint(p)
        if hint.total >= 70:
            pro_score += 10

    if bottleneck_products:
        signals.append(
            {
                "type": "professional",
                "signal": "瓶颈环节关联",
                "detail": f"生产环节：{', '.join(bottleneck_products)}",
            }
        )
    if niche_products:
        signals.append(
            {
                "type": "professional",
                "signal": "Serenity 小众确认",
                "detail": f"小众环节：{', '.join(niche_products)}",
            }
        )
    if (company.get("gross_margin") or 0) >= 0.3:
        pro_score += 15
        signals.append({"type": "professional", "signal": "毛利率支撑", "detail": "具备一定盈利壁垒"})
    if (company.get("market_cap_billion") or 0) < 200:
        pro_score += 10
        signals.append({"type": "professional", "signal": "中小市值弹性", "detail": "符合 Serenity 低拥挤偏好"})

    if retail_score > pro_score + 15:
        verdict = "retail_trap"
        label = "偏散户题材炒作"
        advice = "追高风险较高，建议核实产业壁垒与业绩兑现"
    elif pro_score > retail_score + 15:
        verdict = "professional_alpha"
        label = "偏专业产业 Alpha"
        advice = "产业逻辑支撑度较高，适合中长期跟踪"
    else:
        verdict = "mixed"
        label = "逻辑混合"
        advice = "同时具备题材热度与产业要素，需人工甄别主导逻辑"

    return {
        "stock_code": stock_code,
        "name": company["name"],
        "sector_id": sector_id,
        "verdict": verdict,
        "verdict_label": label,
        "retail_score": round(retail_score, 1),
        "professional_score": round(pro_score, 1),
        "signals": signals,
        "advice": advice,
        "disclaimer": "诊断结果仅供投研参考，不构成投资建议",
    }


def diagnose_sector(store: InMemoryGraphStore, sector_id: str) -> list[dict]:
    results = []
    for code, c in store.companies.items():
        if not any(
            (store.get_product(pid) or {}).get("sector_id") == sector_id for pid in c.get("produces", [])
        ):
            continue
        try:
            results.append(diagnose_company(store, sector_id, code))
        except ValueError:
            continue
    return sorted(results, key=lambda x: -x["professional_score"])
