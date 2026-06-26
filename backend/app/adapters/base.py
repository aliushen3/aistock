"""数据适配器抽象 — 按数据类型拆分。"""

from __future__ import annotations

from typing import Protocol


class IndustryMetricRecord(dict):
    """sector_id, product_id, metric_key, period, value, unit"""


class MarketDailyRecord(dict):
    """stock_code, trade_date, close_price, market_cap_billion, pe_percentile"""


class AnnouncementRecord(dict):
    """ann_id, stock_code, title, ann_date, category, url"""


class FinancialRecord(dict):
    """stock_code, end_date, ann_date, revenue, net_profit, gross_margin, roe, eps"""


class ResearchReportRecord(dict):
    """report_key, stock_code, title, org_name, rating, report_date, url"""


class MarketDataAdapter(Protocol):
    name: str

    def fetch_market_daily(self, stock_codes: list[str]) -> list[MarketDailyRecord]:
        ...


class AnnouncementDataAdapter(Protocol):
    name: str

    def fetch_announcements(self, stock_codes: list[str], limit: int = 20) -> list[AnnouncementRecord]:
        ...


class IndustryMetricsAdapter(Protocol):
    name: str

    def fetch_industry_metrics(self, sector_id: str) -> list[IndustryMetricRecord]:
        ...


class FinancialDataAdapter(Protocol):
    name: str

    def fetch_financials(self, stock_codes: list[str]) -> list[FinancialRecord]:
        ...


class ResearchReportDataAdapter(Protocol):
    name: str

    def fetch_research_reports(self, stock_codes: list[str], limit: int = 20) -> list[ResearchReportRecord]:
        ...


class DataAdapter(Protocol):
    """兼容旧版单体适配器（演示 / 巨潮）。"""

    name: str

    def fetch_industry_metrics(self, sector_id: str) -> list[IndustryMetricRecord]:
        ...

    def fetch_market_daily(self, stock_codes: list[str]) -> list[MarketDailyRecord]:
        ...

    def fetch_announcements(self, stock_codes: list[str], limit: int = 20) -> list[AnnouncementRecord]:
        ...
