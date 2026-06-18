"""双逻辑候选池构建。

- 买方专业池：生产瓶颈环节（hint/confirmed）的公司
- Serenity 逆向池：逆向溯源命中的小众环节公司
- 双逻辑融合池：两池并集，标注共振优先级（见 docs/01-dual-logic-fusion.md §4）

所有候选 status 默认 pending，须经 /candidates/confirm 人工确认方可入正式池。
"""

from __future__ import annotations

from app.services.graph_store import InMemoryGraphStore
from app.services.hint_score import calc_bottleneck_hint
from app.services.serenity_trace import serenity_reverse_trace

# 内存候选池状态：{(sector_id, mode, stock_code): {"status", "reason", "operator"}}
_pool_state: dict[tuple[str, str, str], dict] = {}


def _state_key(sector_id: str, mode: str, code: str) -> tuple[str, str, str]:
    return (sector_id, mode, code)


def get_state(sector_id: str, mode: str, code: str) -> str:
    entry = _pool_state.get(_state_key(sector_id, mode, code))
    return entry["status"] if entry else "pending"


def set_state(sector_id: str, mode: str, code: str, status: str, reason: str, operator: str) -> None:
    _pool_state[_state_key(sector_id, mode, code)] = {
        "status": status,
        "reason": reason,
        "operator": operator,
    }


def build_buy_side_pool(store: InMemoryGraphStore, sector_id: str) -> list[dict]:
    items = []
    for product in store.list_products(sector_id):
        status = product.get("bottleneck_status", "none")
        if status not in ("bottleneck_hint", "bottleneck_confirmed"):
            continue
        hint = calc_bottleneck_hint(product)
        for c in store.companies_producing(product["id"]):
            items.append(
                {
                    "stock_code": c["code"],
                    "name": c["name"],
                    "mode": "buy_side",
                    "role": "buy_side_leader" if c.get("market_rank", 99) <= 2 else "buy_side",
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "hint_type": "bottleneck",
                    "hint_score": hint.total,
                    "bottleneck_status": status,
                    "market_cap_billion": c.get("market_cap_billion"),
                    "analyst_coverage": c.get("analyst_coverage"),
                    "gross_margin": c.get("gross_margin"),
                    "pe_percentile": c.get("pe_percentile"),
                    "rationale": f"生产瓶颈环节「{product['name']}」（{status}，提示分 {hint.total}）",
                }
            )
    return sorted(items, key=lambda x: -x["hint_score"])


def build_serenity_pool(store: InMemoryGraphStore, sector_id: str) -> list[dict]:
    sector = store.get_sector(sector_id)
    terminals = sector.get("terminal_products", []) if sector else []
    paths = serenity_reverse_trace(store, terminals, sector_id)
    items = []
    for path in paths:
        for c in path.companies:
            items.append(
                {
                    "stock_code": c["code"],
                    "name": c["name"],
                    "mode": "serenity",
                    "role": "serenity_niche",
                    "product_id": path.niche_product_id,
                    "product_name": path.niche_product_name,
                    "hint_type": "serenity",
                    "hint_score": path.serenity_hint,
                    "hop_count": path.hop_count,
                    "trace": " → ".join(path.node_names),
                    "market_cap_billion": c.get("market_cap_billion"),
                    "analyst_coverage": c.get("analyst_coverage"),
                    "turnover_percentile": c.get("turnover_percentile"),
                    "tags": c.get("serenity_tags", []),
                    "rationale": f"逆向 {path.hop_count} 跳至小众环节「{path.niche_product_name}」（提示分 {path.serenity_hint}）",
                }
            )
    return sorted(items, key=lambda x: -x["hint_score"])


def build_fusion_pool(store: InMemoryGraphStore, sector_id: str) -> list[dict]:
    buy = {x["stock_code"]: x for x in build_buy_side_pool(store, sector_id)}
    ser = {x["stock_code"]: x for x in build_serenity_pool(store, sector_id)}
    items = []
    for code in set(buy) | set(ser):
        in_buy, in_ser = code in buy, code in ser
        base = buy.get(code) or ser.get(code)
        if in_buy and in_ser:
            priority, tag = "P0", "双逻辑共振"
            score = round((buy[code]["hint_score"] + ser[code]["hint_score"]) / 2, 1)
            rationale = f"买方瓶颈 + Serenity 小众共振：{buy[code]['product_name']}"
        else:
            priority = "P2"
            tag = "买方专业" if in_buy else "Serenity逆向"
            score = base["hint_score"]
            rationale = base["rationale"]
        items.append(
            {
                "stock_code": code,
                "name": base["name"],
                "mode": "fusion",
                "priority": priority,
                "tag": tag,
                "product_name": base["product_name"],
                "hint_score": score,
                "in_buy_side": in_buy,
                "in_serenity": in_ser,
                "market_cap_billion": base.get("market_cap_billion"),
                "rationale": rationale,
            }
        )
    # P0 优先，其次按分数
    return sorted(items, key=lambda x: (x["priority"] != "P0", -x["hint_score"]))


def build_pool(store: InMemoryGraphStore, sector_id: str, mode: str) -> list[dict]:
    if mode == "buy_side":
        items = build_buy_side_pool(store, sector_id)
    elif mode == "serenity":
        items = build_serenity_pool(store, sector_id)
    else:
        items = build_fusion_pool(store, sector_id)
    for it in items:
        it["status"] = get_state(sector_id, mode, it["stock_code"])
    return items
