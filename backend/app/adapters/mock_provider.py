"""Mock 数据适配器 — 组合拆分后的 mock 子适配器。"""

from __future__ import annotations

from app.adapters.announcement.mock_announcement import MockAnnouncementAdapter
from app.adapters.market.mock_market import MockMarketAdapter
from app.adapters.metrics.mock_metrics import MockMetricsAdapter


class MockDataAdapter:
    name = "mock"
    mode = "stub"

    def __init__(self) -> None:
        self._market = MockMarketAdapter()
        self._metrics = MockMetricsAdapter()
        self._announcement = MockAnnouncementAdapter()

    def fetch_industry_metrics(self, sector_id: str) -> list[dict]:
        return self._metrics.fetch_industry_metrics(sector_id)

    def fetch_market_daily(self, stock_codes: list[str]) -> list[dict]:
        return self._market.fetch_market_daily(stock_codes)

    def fetch_announcements(self, stock_codes: list[str], limit: int = 20) -> list[dict]:
        return self._announcement.fetch_announcements(stock_codes, limit=limit)
