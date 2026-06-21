"""数据适配器抽象基类。"""

from __future__ import annotations

from typing import Protocol


class IndustryMetricRecord(dict):
    """sector_id, product_id, metric_key, period, value, unit"""


class MarketDailyRecord(dict):
    """stock_code, trade_date, close_price, market_cap_billion, pe_percentile"""


class AnnouncementRecord(dict):
    """ann_id, stock_code, title, ann_date, category"""


class DataAdapter(Protocol):
    name: str

    def fetch_industry_metrics(self, sector_id: str) -> list[IndustryMetricRecord]:
        ...

    def fetch_market_daily(self, stock_codes: list[str]) -> list[MarketDailyRecord]:
        ...

    def fetch_announcements(self, stock_codes: list[str], limit: int = 20) -> list[AnnouncementRecord]:
        ...
