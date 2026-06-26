"""Mock 行情适配器 — 演示用，从本体公司属性填充。"""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.graph_store import get_store


class MockMarketAdapter:
    name = "mock"

    def fetch_market_daily(self, stock_codes: list[str]) -> list[dict]:
        store = get_store()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = []
        for code in stock_codes:
            c = store.get_company(code)
            if not c:
                continue
            rows.append(
                {
                    "stock_code": code,
                    "trade_date": today,
                    "close_price": None,
                    "market_cap_billion": c.get("market_cap_billion"),
                    "pe_percentile": c.get("pe_percentile"),
                }
            )
        return rows
