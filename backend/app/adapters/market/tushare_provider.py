"""Tushare 行情适配器 — 拉取 A 股日度行情并标准化为 ODS 字段。

设计要点：
- 收盘价用 daily 接口（积分门槛低，覆盖全），取最近可用交易日，自动回退；
- 总市值/PE 用 daily_basic（积分门槛高），尽力而为，无权限则降级为 None；
- 不依赖 trade_cal 取"最新交易日"（其会返回未来日历日，导致查不到数据）。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.adapters.market._utils import (
    is_real_a_share_code,
    normalize_display_code,
    pe_percentile_from_series,
    to_ts_code,
)
from app.config import TUSHARE_RATE_LIMIT_SEC, TUSHARE_TOKEN

logger = logging.getLogger(__name__)

_CN_TZ = timezone(timedelta(hours=8))


class TushareApiError(Exception):
    """Tushare 调用失败。"""


def _load_pro():
    if not TUSHARE_TOKEN:
        raise TushareApiError("未配置 TUSHARE_TOKEN")
    try:
        import tushare as ts
    except ImportError as exc:
        raise TushareApiError("未安装 tushare，请 pip install tushare") from exc
    return ts.pro_api(TUSHARE_TOKEN)


def _sleep_rate_limit() -> None:
    if TUSHARE_RATE_LIMIT_SEC > 0:
        time.sleep(TUSHARE_RATE_LIMIT_SEC)


def _today_cn() -> str:
    return datetime.now(_CN_TZ).strftime("%Y%m%d")


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest_daily(pro: Any, ts_code: str) -> tuple[str, float] | None:
    """最近可用交易日的 (trade_date, close)。"""
    today = _today_cn()
    start = (datetime.strptime(today, "%Y%m%d") - timedelta(days=15)).strftime("%Y%m%d")
    _sleep_rate_limit()
    df = pro.daily(ts_code=ts_code, start_date=start, end_date=today, fields="trade_date,close")
    if df is None or df.empty:
        return None
    df = df.sort_values("trade_date")
    row = df.iloc[-1]
    close = _to_float(row["close"])
    if close is None:
        return None
    return str(row["trade_date"]), close


def _daily_basic_metrics(pro: Any, ts_code: str, trade_date: str) -> tuple[float | None, float | None]:
    """(market_cap_billion, pe_percentile)，daily_basic 无权限时降级 (None, None)。"""
    try:
        _sleep_rate_limit()
        basic = pro.daily_basic(ts_code=ts_code, trade_date=trade_date, fields="trade_date,total_mv,pe")
    except Exception as exc:
        logger.warning("Tushare daily_basic 不可用 %s: %s", ts_code, exc)
        return None, None
    if basic is None or basic.empty:
        return None, None
    total_mv = _to_float(basic.iloc[0].get("total_mv"))
    market_cap_billion = total_mv / 10000 if total_mv is not None else None

    start = (datetime.strptime(trade_date, "%Y%m%d") - timedelta(days=365 * 5)).strftime("%Y%m%d")
    pe_values: list[float] = []
    try:
        _sleep_rate_limit()
        hist = pro.daily_basic(ts_code=ts_code, start_date=start, end_date=trade_date, fields="trade_date,pe")
        if hist is not None and not hist.empty:
            hist = hist.sort_values("trade_date")
            for raw in hist["pe"].tolist():
                val = _to_float(raw)
                if val is not None and val > 0:
                    pe_values.append(val)
    except Exception as exc:
        logger.warning("Tushare PE 历史不可用 %s: %s", ts_code, exc)
    return market_cap_billion, pe_percentile_from_series(pe_values)


def _fetch_code_row(pro: Any, ts_code: str) -> dict | None:
    latest = _latest_daily(pro, ts_code)
    if latest is None:
        return None
    trade_date, close_price = latest
    market_cap_billion, pe_percentile = _daily_basic_metrics(pro, ts_code, trade_date)
    return {
        "stock_code": normalize_display_code(ts_code),
        "trade_date": datetime.strptime(trade_date, "%Y%m%d").strftime("%Y-%m-%d"),
        "close_price": close_price,
        "market_cap_billion": market_cap_billion,
        "pe_percentile": pe_percentile,
    }


def fetch_market_rows(stock_codes: list[str]) -> list[dict]:
    """可被测试 monkeypatch 的核心抓取逻辑（逐只单股请求）。"""
    codes = [normalize_display_code(c) for c in stock_codes if is_real_a_share_code(c)]
    if not codes:
        return []
    pro = _load_pro()
    rows: list[dict] = []
    missing: list[str] = []
    for code in codes:
        ts_code = to_ts_code(code)
        try:
            row = _fetch_code_row(pro, ts_code)
        except Exception as exc:
            logger.warning("Tushare 拉取 %s 失败: %s", ts_code, exc)
            missing.append(code)
            continue
        if row:
            rows.append(row)
        else:
            missing.append(code)
    if missing:
        logger.warning("Tushare 未找到部分代码: %s", missing)
    return rows


class TushareMarketAdapter:
    name = "tushare"

    def __init__(self) -> None:
        try:
            _load_pro()
            self.mode = "live"
        except TushareApiError:
            self.mode = "stub"

    def fetch_market_daily(self, stock_codes: list[str]) -> list[dict]:
        try:
            rows = fetch_market_rows(stock_codes)
        except TushareApiError:
            raise
        except Exception as exc:
            raise TushareApiError(str(exc)) from exc
        if not rows:
            raise TushareApiError("Tushare 行情响应为空")
        return rows
