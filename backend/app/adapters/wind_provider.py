"""Wind 数据适配器 — live 模式经 REST 网关拉取，失败时降级 mock。"""

from __future__ import annotations

import logging
import os

from app.adapters.mock_provider import MockDataAdapter
from app.adapters.wind_client import WindApiError, WindClient

logger = logging.getLogger(__name__)


class WindDataAdapter:
    name = "wind"

    def __init__(self) -> None:
        self._fallback = MockDataAdapter()
        self.api_key = os.getenv("WIND_API_KEY", "")
        self.mode = "live" if self.api_key else "stub"
        self._client = WindClient(api_key=self.api_key) if self.mode == "live" else None

    def fetch_industry_metrics(self, sector_id: str) -> list[dict]:
        if self.mode != "live" or self._client is None:
            return self._fallback.fetch_industry_metrics(sector_id)
        try:
            return self._client.fetch_industry_metrics(sector_id)
        except WindApiError as exc:
            logger.warning("Wind live metrics 失败，降级 mock: %s", exc)
            return self._fallback.fetch_industry_metrics(sector_id)

    def fetch_market_daily(self, stock_codes: list[str]) -> list[dict]:
        if self.mode != "live" or self._client is None:
            return self._fallback.fetch_market_daily(stock_codes)
        try:
            return self._client.fetch_market_daily(stock_codes)
        except WindApiError as exc:
            logger.warning("Wind live market 失败，降级 mock: %s", exc)
            return self._fallback.fetch_market_daily(stock_codes)

    def fetch_announcements(self, stock_codes: list[str], limit: int = 20) -> list[dict]:
        if self.mode != "live" or self._client is None:
            return self._fallback.fetch_announcements(stock_codes, limit=limit)
        try:
            return self._client.fetch_announcements(stock_codes, limit=limit)
        except WindApiError as exc:
            logger.warning("Wind live announcements 失败，降级 mock: %s", exc)
            return self._fallback.fetch_announcements(stock_codes, limit=limit)
