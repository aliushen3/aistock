from __future__ import annotations

from app.services.a_share_data_source import fetch_eastmoney_reports


class EastmoneyResearchAdapter:
    name = "eastmoney"
    mode = "live"

    def fetch_research_reports(self, stock_codes: list[str], limit: int = 20) -> list[dict]:
        rows: list[dict] = []
        for code in stock_codes:
            rows.extend(fetch_eastmoney_reports(code, max_pages=1)[:limit])
        return rows
