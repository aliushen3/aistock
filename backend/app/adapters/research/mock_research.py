"""Mock 研报适配器 — 演示环境返回空列表。"""

from __future__ import annotations


class MockResearchAdapter:
    name = "mock"

    def fetch_research_reports(self, stock_codes: list[str], limit: int = 20) -> list[dict]:
        return []
