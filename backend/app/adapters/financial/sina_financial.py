from __future__ import annotations

from app.adapters.market._utils import is_real_a_share_code, normalize_display_code
from app.services.a_share_data_source import AShareDataError, build_financial_snapshot


class SinaFinancialAdapter:
    name = "sina"
    mode = "live"

    def fetch_financials(self, stock_codes: list[str]) -> list[dict]:
        rows: list[dict] = []
        for raw in stock_codes:
            code = normalize_display_code(raw)
            if not is_real_a_share_code(code):
                continue
            try:
                snap = build_financial_snapshot(code)
            except AShareDataError:
                continue
            period = snap.get("report_period")
            if not period:
                continue
            rows.append(
                {
                    "stock_code": snap["stock_code"],
                    "end_date": period,
                    "ann_date": None,
                    "revenue": snap.get("revenue"),
                    "net_profit": snap.get("net_profit"),
                    "gross_margin": snap.get("gross_margin"),
                    "roe": snap.get("roe"),
                    "eps": snap.get("eps"),
                }
            )
        return rows
