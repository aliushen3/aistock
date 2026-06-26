"""Mock 财报适配器 — 演示环境返回空列表。"""

from __future__ import annotations


class MockFinancialAdapter:
    name = "mock"

    def fetch_financials(self, stock_codes: list[str]) -> list[dict]:
        return []
