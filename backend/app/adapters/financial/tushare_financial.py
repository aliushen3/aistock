"""Tushare 财报适配器 — income + fina_indicator（需 2000 积分）。

输出对齐 ods_financial_statement：取最近一期报告。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.adapters.market._utils import is_real_a_share_code, normalize_display_code, to_ts_code
from app.config import TUSHARE_RATE_LIMIT_SEC, TUSHARE_TOKEN

logger = logging.getLogger(__name__)


class TushareFinancialError(Exception):
    """Tushare 财报调用失败。"""


def _load_pro():
    if not TUSHARE_TOKEN:
        raise TushareFinancialError("未配置 TUSHARE_TOKEN")
    try:
        import tushare as ts
    except ImportError as exc:
        raise TushareFinancialError("未安装 tushare，请 pip install tushare") from exc
    return ts.pro_api(TUSHARE_TOKEN)


def _sleep_rate_limit() -> None:
    if TUSHARE_RATE_LIMIT_SEC > 0:
        time.sleep(TUSHARE_RATE_LIMIT_SEC)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest_indicator(pro: Any, ts_code: str) -> dict:
    _sleep_rate_limit()
    df = pro.fina_indicator(
        ts_code=ts_code,
        fields="ts_code,end_date,ann_date,eps,roe,grossprofit_margin",
    )
    if df is None or df.empty:
        return {}
    df = df.sort_values("end_date")
    return df.iloc[-1].to_dict()


def _income_for_period(pro: Any, ts_code: str, end_date: str) -> dict:
    _sleep_rate_limit()
    df = pro.income(
        ts_code=ts_code,
        period=end_date,
        fields="ts_code,end_date,revenue,n_income",
    )
    if df is None or df.empty:
        return {}
    return df.iloc[0].to_dict()


def _fetch_one(pro: Any, ts_code: str) -> dict | None:
    ind = _latest_indicator(pro, ts_code)
    end_date = ind.get("end_date")
    if not end_date:
        return None
    income = _income_for_period(pro, ts_code, str(end_date))
    gross_raw = _to_float(ind.get("grossprofit_margin"))
    roe_raw = _to_float(ind.get("roe"))
    return {
        "stock_code": normalize_display_code(ts_code),
        "end_date": str(end_date),
        "ann_date": str(ind.get("ann_date")) if ind.get("ann_date") else None,
        "revenue": _to_float(income.get("revenue")),
        "net_profit": _to_float(income.get("n_income")),
        "gross_margin": gross_raw / 100 if gross_raw is not None else None,
        "roe": roe_raw / 100 if roe_raw is not None else None,
        "eps": _to_float(ind.get("eps")),
    }


def fetch_financial_rows(stock_codes: list[str]) -> list[dict]:
    """可被测试 monkeypatch 的核心抓取逻辑。"""
    codes = [normalize_display_code(c) for c in stock_codes if is_real_a_share_code(c)]
    if not codes:
        return []
    pro = _load_pro()
    rows: list[dict] = []
    missing: list[str] = []
    for code in codes:
        ts_code = to_ts_code(code)
        try:
            row = _fetch_one(pro, ts_code)
        except Exception as exc:
            logger.warning("Tushare 财报拉取 %s 失败: %s", ts_code, exc)
            missing.append(code)
            continue
        if row:
            rows.append(row)
        else:
            missing.append(code)
    if missing:
        logger.warning("Tushare 财报未找到部分代码: %s", missing)
    return rows


class TushareFinancialAdapter:
    name = "tushare"

    def __init__(self) -> None:
        try:
            _load_pro()
            self.mode = "live"
        except TushareFinancialError:
            self.mode = "stub"

    def fetch_financials(self, stock_codes: list[str]) -> list[dict]:
        try:
            rows = fetch_financial_rows(stock_codes)
        except TushareFinancialError:
            raise
        except Exception as exc:
            raise TushareFinancialError(str(exc)) from exc
        if not rows:
            raise TushareFinancialError("Tushare 财报响应为空")
        return rows
