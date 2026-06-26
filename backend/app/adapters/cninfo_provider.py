"""巨潮资讯适配器 — live 模式经 REST 网关拉取公告。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.adapters.cninfo_client import CninfoApiError, CninfoClient
from app.adapters.metrics.mock_metrics import MockMetricsAdapter
from app.adapters.market.mock_market import MockMarketAdapter
from app.config import CNINFO_API_URL

logger = logging.getLogger(__name__)


class CninfoDataAdapter:
    name = "cninfo"

    def __init__(self) -> None:
        self._metrics = MockMetricsAdapter()
        self._market = MockMarketAdapter()
        self.api_url = CNINFO_API_URL
        self.mode = "live" if self.api_url else "stub"
        self._client = CninfoClient() if self.mode == "live" else None

    def fetch_industry_metrics(self, sector_id: str) -> list[dict]:
        return self._metrics.fetch_industry_metrics(sector_id)

    def fetch_market_daily(self, stock_codes: list[str]) -> list[dict]:
        return self._market.fetch_market_daily(stock_codes)

    def fetch_announcements(self, stock_codes: list[str], limit: int = 20) -> list[dict]:
        if self.mode == "live" and self._client is not None:
            try:
                rows = self._client.fetch_announcements(stock_codes, limit=limit)
                if rows:
                    return rows
            except CninfoApiError as exc:
                logger.warning("巨潮 live 公告失败，降级 stub: %s", exc)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = []
        for i, code in enumerate(stock_codes[:limit]):
            rows.append(
                {
                    "ann_id": f"cninfo_stub_{code}_{i}",
                    "stock_code": code,
                    "title": f"[stub] {code} 扩产/产能相关公告",
                    "ann_date": today,
                    "category": "capacity_expansion",
                }
            )
        return rows
