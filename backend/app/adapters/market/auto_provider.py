"""自动降级行情适配器 — Tushare 主源 → AkShare 备源。

业界推荐：生产以 Tushare Pro（稳定、合规、日线免费积分够用）为主，
AkShare（免费无 token）为备，主源不可用或为空时自动降级。
"""

from __future__ import annotations

import logging

from app.adapters.market.akshare_provider import AkshareMarketAdapter
from app.adapters.market.tushare_provider import TushareMarketAdapter

logger = logging.getLogger(__name__)


class AutoMarketAdapter:
    name = "auto"

    def __init__(self) -> None:
        self._tushare = TushareMarketAdapter()
        self._akshare = AkshareMarketAdapter()
        self.mode = "live" if (self._tushare.mode == "live" or self._akshare.mode == "live") else "stub"

    def fetch_market_daily(self, stock_codes: list[str]) -> list[dict]:
        errors: list[str] = []
        if self._tushare.mode == "live":
            try:
                return self._tushare.fetch_market_daily(stock_codes)
            except Exception as exc:
                errors.append(f"tushare: {exc}")
                logger.warning("auto 行情主源 tushare 失败，降级 akshare: %s", exc)
        try:
            return self._akshare.fetch_market_daily(stock_codes)
        except Exception as exc:
            errors.append(f"akshare: {exc}")
            raise RuntimeError("auto 行情主备源均失败 -> " + "; ".join(errors)) from exc
