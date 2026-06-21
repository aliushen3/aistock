"""Serenity 逆向溯源智能体 — 路径扫描 → 小众环节确认提案。"""

from __future__ import annotations

import uuid

from app.ontology.object_store import get_product
from app.services.graph_store import get_store
from app.services.object_set_alerts import push_serenity_recommendation_alerts
from app.services.serenity_recommendations import save_recommendations
from app.services.serenity_trace import serenity_reverse_trace
from app.services.workflow import is_sector_confirmed


def run_serenity_path_agent(
    sector_id: str,
    min_serenity_hint: float = 50.0,
    operator: str = "analyst",
) -> dict:
    store = get_store()
    sector = store.get_sector(sector_id)
    if sector is None:
        raise ValueError(f"赛道不存在: {sector_id}")

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    terminal_ids = sector.get("terminal_products") or [
        p["id"] for p in store.list_products(sector_id) if p.get("layer") == "terminal"
    ]
    if not terminal_ids:
        terminal_ids = [p["id"] for p in store.list_products(sector_id)[:2]]

    paths = serenity_reverse_trace(store, terminal_ids, sector_id)
    proposals: list[dict] = []

    for path in paths:
        product = get_product(path.niche_product_id) or store.get_product(path.niche_product_id)
        if product and product.get("serenity_niche_confirmed"):
            continue
        if path.serenity_hint < min_serenity_hint:
            continue
        company_names = [c.get("name", c.get("stock_code", "")) for c in path.companies[:3]]
        proposals.append(
            {
                "path_id": path.path_id,
                "niche_product_id": path.niche_product_id,
                "niche_product_name": path.niche_product_name,
                "serenity_hint": path.serenity_hint,
                "hop_count": path.hop_count,
                "node_names": path.node_names,
                "companies": path.companies[:5],
                "rationale": (
                    f"逆向 {path.hop_count} 跳至「{path.niche_product_name}」"
                    f"（Serenity 提示分 {path.serenity_hint}）；"
                    f"路径：{' → '.join(path.node_names)}；"
                    f"关联标的：{', '.join(company_names) or '待补全'}"
                ),
            }
        )

    saved = save_recommendations(
        run_id=run_id,
        sector_id=sector_id,
        items=proposals,
        agent_mode="trace_v1",
        operator=operator,
    )
    alerts = push_serenity_recommendation_alerts(saved, run_id)

    return {
        "run_id": run_id,
        "agent": "serenity_path_v1",
        "agent_mode": "trace_v1",
        "sector_id": sector_id,
        "sector_confirmed": is_sector_confirmed(sector_id),
        "path_count": len(paths),
        "recommendations": saved,
        "alerts_pushed": alerts,
        "disclaimer": "路径提案须经 ConfirmSerenityNiche 人工确认后方可入 Serenity 池",
    }
