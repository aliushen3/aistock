"""知识保鲜（主线二）— 每条 confirmed 知识有半衰期，过期自动降级。

确定性纯函数；now 作参数注入便于测试。对齐 docs/DESIGN.md §5.7 / docs/02-knowledge-engineering.md §2.4。

状态机：fresh → (超过 half_life/2) aging → (超过 valid_until=last_verified+half_life) stale
"""

from __future__ import annotations

from datetime import date, datetime, timezone

# 按属性类别的半衰期参考（天），可配置
HALF_LIFE_DAYS = {
    "capacity": 90,       # 产能 / 供需缺口 / 涨价
    "landscape": 180,     # CR4 / 竞争格局 / 机构覆盖
    "cycle": 365,         # 扩产周期 / 认证周期
    "relation": 720,      # 上下游关系结构
}
DEFAULT_HALF_LIFE_DAYS = 180


def _parse(ts) -> datetime | None:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    if isinstance(ts, date):
        return datetime(ts.year, ts.month, ts.day, tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def compute_freshness(
    last_verified_at, half_life_days: int | None = None, now: datetime | None = None
) -> dict:
    """返回 {freshness, valid_until, age_days}。无 last_verified_at → unknown。"""
    half_life = int(half_life_days or DEFAULT_HALF_LIFE_DAYS)
    verified = _parse(last_verified_at)
    if verified is None:
        return {"freshness": "unknown", "valid_until": None, "age_days": None, "half_life_days": half_life}

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age_days = (now - verified).days
    valid_until = verified.fromordinal(verified.toordinal() + half_life).date().isoformat()

    if age_days >= half_life:
        freshness = "stale"
    elif age_days >= half_life / 2:
        freshness = "aging"
    else:
        freshness = "fresh"

    return {
        "freshness": freshness,
        "valid_until": valid_until,
        "age_days": age_days,
        "half_life_days": half_life,
    }


def product_freshness(product: dict, now: datetime | None = None) -> dict:
    """产品级保鲜：读取 seed 的 last_verified_at / half_life_days。"""
    return compute_freshness(
        product.get("last_verified_at"),
        product.get("half_life_days", HALF_LIFE_DAYS["capacity"]),
        now=now,
    )


def is_stale(product: dict, now: datetime | None = None) -> bool:
    return product_freshness(product, now).get("freshness") == "stale"
