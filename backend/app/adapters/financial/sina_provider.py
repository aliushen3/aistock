from __future__ import annotations

from app.services.a_share_data_source import build_financial_snapshot


class SinaFinancialAdapter:
    name = "sina"
    mode = "live"

    def fetch_financials(self, stock_codes: list[str]) -> list[dict]:
        rows: list[dict] = []
        for code in stock_codes:
            snapshot = build_financial_snapshot(code)
            if not snapshot.get("report_period"):
                continue
            rows.append(
                {
                    "stock_code": snapshot["stock_code"],
                    "end_date": snapshot["report_period"].replace("-", ""),
                    "ann_date": None,
                    "revenue": snapshot.get("revenue"),
                    "net_profit": snapshot.get("net_profit"),
                    "gross_margin": snapshot.get("gross_margin"),
                    "roe": snapshot.get("roe"),
                    "eps": snapshot.get("eps"),
                }
            )
        return rows
