from __future__ import annotations

from datetime import datetime, timezone

from app.services.a_share_data_source import fetch_tencent_quotes


class TencentMarketAdapter:
    name = "tencent"
    mode = "live"

    def fetch_market_daily(self, stock_codes: list[str]) -> list[dict]:
        quotes = fetch_tencent_quotes(stock_codes)
        trade_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows: list[dict] = []
        for code, quote in quotes.items():
            rows.append(
                {
                    "stock_code": code,
                    "trade_date": trade_date,
                    "close_price": quote.get("price"),
                    "market_cap_billion": quote.get("mcap_yi"),
                    "pe_percentile": None,
                }
            )
        return rows
