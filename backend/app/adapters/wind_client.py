"""Wind REST 网关客户端 — 对接可配置的 Wind 代理服务。"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import WIND_API_KEY, WIND_API_TIMEOUT, WIND_API_URL


class WindApiError(Exception):
    """Wind API 调用失败。"""


class WindClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or WIND_API_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else WIND_API_KEY
        self.timeout = timeout if timeout is not None else WIND_API_TIMEOUT

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, method: str, path: str, params: dict | None = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(method, url, params=params, headers=self._headers())
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise WindApiError(str(exc)) from exc

    @staticmethod
    def _normalize_metrics(payload: Any, sector_id: str) -> list[dict]:
        items = payload.get("items", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise WindApiError("Wind 指标响应格式无效")
        rows: list[dict] = []
        for item in items:
            if not isinstance(item, dict) or "metric_key" not in item:
                continue
            rows.append(
                {
                    "sector_id": item.get("sector_id", sector_id),
                    "product_id": item.get("product_id"),
                    "metric_key": item["metric_key"],
                    "period": item.get("period", ""),
                    "value": item["value"],
                    "unit": item.get("unit", ""),
                }
            )
        return rows

    @staticmethod
    def _normalize_market(payload: Any) -> list[dict]:
        items = payload.get("items", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise WindApiError("Wind 行情响应格式无效")
        rows: list[dict] = []
        for item in items:
            if not isinstance(item, dict) or "stock_code" not in item:
                continue
            rows.append(
                {
                    "stock_code": item["stock_code"],
                    "trade_date": item.get("trade_date", ""),
                    "close_price": item.get("close_price"),
                    "market_cap_billion": item.get("market_cap_billion"),
                    "pe_percentile": item.get("pe_percentile"),
                }
            )
        return rows

    @staticmethod
    def _normalize_announcements(payload: Any) -> list[dict]:
        items = payload.get("items", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise WindApiError("Wind 公告响应格式无效")
        rows: list[dict] = []
        for item in items:
            if not isinstance(item, dict) or "stock_code" not in item:
                continue
            rows.append(
                {
                    "ann_id": item.get("ann_id", ""),
                    "stock_code": item["stock_code"],
                    "title": item.get("title", ""),
                    "ann_date": item.get("ann_date", ""),
                    "category": item.get("category", "general"),
                }
            )
        return rows

    def fetch_industry_metrics(self, sector_id: str) -> list[dict]:
        payload = self._request("GET", "/v1/industry-metrics", {"sector_id": sector_id})
        rows = self._normalize_metrics(payload, sector_id)
        if not rows:
            raise WindApiError("Wind 指标响应为空")
        return rows

    def fetch_market_daily(self, stock_codes: list[str]) -> list[dict]:
        payload = self._request(
            "GET",
            "/v1/market-daily",
            {"stock_codes": ",".join(stock_codes)},
        )
        rows = self._normalize_market(payload)
        if not rows:
            raise WindApiError("Wind 行情响应为空")
        return rows

    def fetch_announcements(self, stock_codes: list[str], limit: int = 20) -> list[dict]:
        payload = self._request(
            "GET",
            "/v1/announcements",
            {"stock_codes": ",".join(stock_codes), "limit": limit},
        )
        return self._normalize_announcements(payload)
