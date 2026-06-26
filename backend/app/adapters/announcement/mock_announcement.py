"""Mock 公告适配器 — 演示环境返回空列表。"""

from __future__ import annotations


class MockAnnouncementAdapter:
    name = "mock"

    def fetch_announcements(self, stock_codes: list[str], limit: int = 20) -> list[dict]:
        return []
