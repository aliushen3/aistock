"""巨潮 REST 网关客户端 — 对接可配置的巨潮代理服务。"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import CNINFO_API_TIMEOUT, CNINFO_API_URL


class CninfoApiError(Exception):
    """巨潮 API 调用失败。"""


class CninfoClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or CNINFO_API_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else CNINFO_API_TIMEOUT

    def _request(self, method: str, path: str, params: dict | None = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(method, url, params=params, headers={"Accept": "application/json"})
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise CninfoApiError(str(exc)) from exc

    @staticmethod
    def _normalize_announcements(payload: Any) -> list[dict]:
        items = payload.get("items", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise CninfoApiError("巨潮公告响应格式无效")
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

    def fetch_announcements(self, stock_codes: list[str], limit: int = 20) -> list[dict]:
        payload = self._request(
            "GET",
            "/v1/announcements",
            {"stock_codes": ",".join(stock_codes), "limit": limit},
        )
        return self._normalize_announcements(payload)
