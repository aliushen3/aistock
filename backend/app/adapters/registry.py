"""适配器注册表 — 按数据类型拆分。"""

from __future__ import annotations

from app.adapters.announcement.akshare_announcement import AkshareAnnouncementAdapter
from app.adapters.announcement.mock_announcement import MockAnnouncementAdapter
from app.adapters.cninfo_provider import CninfoDataAdapter
from app.adapters.constituent.akshare_constituent import AkshareConstituentAdapter
from app.adapters.constituent.mock_constituent import MockConstituentAdapter
from app.adapters.financial.mock_financial import MockFinancialAdapter
from app.adapters.financial.tushare_financial import TushareFinancialAdapter
from app.adapters.market.akshare_provider import AkshareMarketAdapter
from app.adapters.market.auto_provider import AutoMarketAdapter
from app.adapters.market.mock_market import MockMarketAdapter
from app.adapters.market.tushare_provider import TushareMarketAdapter
from app.adapters.metrics.akshare_metrics import AkshareMetricsAdapter
from app.adapters.metrics.mock_metrics import MockMetricsAdapter
from app.adapters.mock_provider import MockDataAdapter
from app.adapters.research.em_research import EmResearchAdapter
from app.adapters.research.mock_research import MockResearchAdapter
from app.config import (
    DATA_ADAPTER,
    DATA_ADAPTER_ANNOUNCEMENT,
    DATA_ADAPTER_CONSTITUENT,
    DATA_ADAPTER_FINANCIAL,
    DATA_ADAPTER_MARKET,
    DATA_ADAPTER_METRICS,
    DATA_ADAPTER_RESEARCH,
)

_market_adapters = {
    "mock": MockMarketAdapter(),
    "akshare": AkshareMarketAdapter(),
    "tushare": TushareMarketAdapter(),
    "auto": AutoMarketAdapter(),
}

_announcement_adapters = {
    "mock": MockAnnouncementAdapter(),
    "cninfo": CninfoDataAdapter(),
    "akshare": AkshareAnnouncementAdapter(),
}

_metrics_adapters = {
    "mock": MockMetricsAdapter(),
    "akshare": AkshareMetricsAdapter(),
}

_financial_adapters = {
    "mock": MockFinancialAdapter(),
    "tushare": TushareFinancialAdapter(),
}

_research_adapters = {
    "mock": MockResearchAdapter(),
    "em": EmResearchAdapter(),
}

_constituent_adapters = {
    "mock": MockConstituentAdapter(),
    "akshare": AkshareConstituentAdapter(),
}

_legacy_adapters = {
    "mock": MockDataAdapter(),
    "cninfo": CninfoDataAdapter(),
}


def get_market_adapter(name: str | None = None):
    key = (name or DATA_ADAPTER_MARKET).lower()
    adapter = _market_adapters.get(key)
    if adapter is None:
        raise ValueError(f"未知行情适配器: {key}，可用: {list(_market_adapters.keys())}")
    return adapter


def get_announcement_adapter(name: str | None = None):
    key = (name or DATA_ADAPTER_ANNOUNCEMENT).lower()
    adapter = _announcement_adapters.get(key)
    if adapter is None:
        raise ValueError(f"未知公告适配器: {key}，可用: {list(_announcement_adapters.keys())}")
    return adapter


def get_metrics_adapter(name: str | None = None):
    key = (name or DATA_ADAPTER_METRICS).lower()
    adapter = _metrics_adapters.get(key)
    if adapter is None:
        raise ValueError(f"未知产业指标适配器: {key}，可用: {list(_metrics_adapters.keys())}")
    return adapter


def get_financial_adapter(name: str | None = None):
    key = (name or DATA_ADAPTER_FINANCIAL).lower()
    adapter = _financial_adapters.get(key)
    if adapter is None:
        raise ValueError(f"未知财报适配器: {key}，可用: {list(_financial_adapters.keys())}")
    return adapter


def get_research_adapter(name: str | None = None):
    key = (name or DATA_ADAPTER_RESEARCH).lower()
    adapter = _research_adapters.get(key)
    if adapter is None:
        raise ValueError(f"未知研报适配器: {key}，可用: {list(_research_adapters.keys())}")
    return adapter


def get_constituent_adapter(name: str | None = None):
    key = (name or DATA_ADAPTER_CONSTITUENT).lower()
    adapter = _constituent_adapters.get(key)
    if adapter is None:
        raise ValueError(f"未知成分股适配器: {key}，可用: {list(_constituent_adapters.keys())}")
    return adapter


def get_adapter(name: str | None = None):
    """兼容旧版单体适配器选择（演示 / 巨潮）。"""
    key = (name or DATA_ADAPTER).lower()
    adapter = _legacy_adapters.get(key)
    if adapter is None:
        if key in _market_adapters:
            return _CompositeAdapter(market=_market_adapters[key])
        raise ValueError(
            f"未知数据适配器: {key}，可用: {list(_legacy_adapters.keys()) + list(_market_adapters.keys())}"
        )
    return adapter


class _CompositeAdapter:
    """将拆分后的行情适配器包装为旧接口。"""

    def __init__(self, market) -> None:
        self.name = market.name
        self.mode = getattr(market, "mode", "default")
        self._market = market
        self._metrics = MockMetricsAdapter()
        self._announcement = MockAnnouncementAdapter()

    def fetch_industry_metrics(self, sector_id: str) -> list[dict]:
        return self._metrics.fetch_industry_metrics(sector_id)

    def fetch_market_daily(self, stock_codes: list[str]) -> list[dict]:
        return self._market.fetch_market_daily(stock_codes)

    def fetch_announcements(self, stock_codes: list[str], limit: int = 20) -> list[dict]:
        return self._announcement.fetch_announcements(stock_codes, limit=limit)


def list_adapters() -> list[dict]:
    from app.config import CNINFO_API_URL, TUSHARE_TOKEN

    items: list[dict] = []
    for kind, mapping, default in (
        ("market", _market_adapters, DATA_ADAPTER_MARKET),
        ("announcement", _announcement_adapters, DATA_ADAPTER_ANNOUNCEMENT),
        ("metrics", _metrics_adapters, DATA_ADAPTER_METRICS),
        ("financial", _financial_adapters, DATA_ADAPTER_FINANCIAL),
        ("research", _research_adapters, DATA_ADAPTER_RESEARCH),
        ("constituent", _constituent_adapters, DATA_ADAPTER_CONSTITUENT),
    ):
        for adapter in mapping.values():
            detail: dict = {
                "kind": kind,
                "name": adapter.name,
                "mode": getattr(adapter, "mode", "default"),
                "default": adapter.name == default,
            }
            if adapter.name == "tushare" or (kind == "market" and adapter.name == "auto"):
                detail["tushare_configured"] = bool(TUSHARE_TOKEN)
            if kind == "announcement" and adapter.name == "cninfo":
                detail["live_configured"] = bool(CNINFO_API_URL)
                detail["gateway_url"] = CNINFO_API_URL or None
            items.append(detail)
    for adapter in _legacy_adapters.values():
        detail = {
            "kind": "legacy",
            "name": adapter.name,
            "mode": getattr(adapter, "mode", "default"),
            "default": adapter.name == DATA_ADAPTER,
        }
        if adapter.name == "cninfo":
            detail["live_configured"] = bool(CNINFO_API_URL)
            detail["gateway_url"] = CNINFO_API_URL or None
        items.append(detail)
    return items
