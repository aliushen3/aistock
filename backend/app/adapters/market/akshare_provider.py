"""AkShare 行情适配器 — 单股拉取 A 股日度行情并标准化为 ODS 字段。

设计要点（业界稳定性实践）：
- 用单股接口 stock_individual_info_em，避免 stock_zh_a_spot_em 全市场扫描导致的慢/易封；
- 强制 IPv4 + 重试退避，规避免费源 IPv6 握手重置与偶发限流；
- PE 历史分位为尽力而为，源不可达时降级为 None，不阻断主流程。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.adapters.market._net import ensure_ipv4, with_retry
from app.adapters.market._utils import (
    is_real_a_share_code,
    normalize_display_code,
    pe_percentile_from_series,
)
from app.config import AKSHARE_RATE_LIMIT_SEC

logger = logging.getLogger(__name__)


class AkshareApiError(Exception):
    """AkShare 调用失败。"""


def _load_akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise AkshareApiError("未安装 akshare，请 pip install akshare") from exc
    return ak


def _sleep_rate_limit() -> None:
    if AKSHARE_RATE_LIMIT_SEC > 0:
        time.sleep(AKSHARE_RATE_LIMIT_SEC)


def _info_map(symbol: str) -> dict[str, Any]:
    """东财个股信息（单股，一次请求）→ {item: value}。"""
    ak = _load_akshare()
    ensure_ipv4()
    _sleep_rate_limit()
    df = with_retry(lambda: ak.stock_individual_info_em(symbol=symbol), label=f"akshare info {symbol}")
    if df is None or getattr(df, "empty", True):
        return {}
    return {str(r["item"]): r["value"] for _, r in df.iterrows()}


def _pe_history(symbol: str) -> list[float]:
    """乐咕乐股历史 PE（尽力而为，失败返回空）。"""
    ak = _load_akshare()
    ensure_ipv4()
    _sleep_rate_limit()
    try:
        df = with_retry(lambda: ak.stock_a_lg_indicator(stock=symbol), label=f"akshare pe {symbol}")
    except Exception as exc:
        logger.warning("AkShare PE 历史不可用 %s: %s", symbol, exc)
        return []
    if df is None or getattr(df, "empty", True):
        return []
    col = "pe" if "pe" in df.columns else ("市盈率" if "市盈率" in df.columns else None)
    if not col:
        return []
    values: list[float] = []
    for raw in df[col].tolist():
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if val > 0:
            values.append(val)
    return values


def _to_float(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fetch_one(code: str, trade_date: str) -> dict | None:
    info = _info_map(code)
    if not info:
        return None
    close_price = _to_float(info.get("最新"))
    total_mv = _to_float(info.get("总市值"))
    market_cap_billion = total_mv / 1e8 if total_mv is not None else None
    pe_percentile = pe_percentile_from_series(_pe_history(code))
    return {
        "stock_code": code,
        "trade_date": trade_date,
        "close_price": close_price,
        "market_cap_billion": market_cap_billion,
        "pe_percentile": pe_percentile,
    }


def fetch_market_rows(stock_codes: list[str]) -> list[dict]:
    """可被测试 monkeypatch 的核心抓取逻辑（逐只单股请求）。"""
    codes = [normalize_display_code(c) for c in stock_codes if is_real_a_share_code(c)]
    if not codes:
        return []
    trade_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows: list[dict] = []
    missing: list[str] = []
    for code in codes:
        try:
            row = _fetch_one(code, trade_date)
        except Exception as exc:
            logger.warning("AkShare 拉取 %s 失败: %s", code, exc)
            missing.append(code)
            continue
        if row:
            rows.append(row)
        else:
            missing.append(code)
    if missing:
        logger.warning("AkShare 未找到部分代码: %s", missing)
    return rows


class AkshareMarketAdapter:
    name = "akshare"

    def __init__(self) -> None:
        try:
            _load_akshare()
            self.mode = "live"
        except AkshareApiError:
            self.mode = "stub"

    def fetch_market_daily(self, stock_codes: list[str]) -> list[dict]:
        try:
            rows = fetch_market_rows(stock_codes)
        except Exception as exc:
            raise AkshareApiError(str(exc)) from exc
        if not rows:
            raise AkshareApiError("AkShare 行情响应为空")
        return rows
