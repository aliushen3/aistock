from __future__ import annotations

from app.adapters.market._utils import is_real_a_share_code, normalize_display_code
from app.services.a_share_data_source import AShareDataError, build_financial_snapshot


def _ratio(value: float | None) -> float | None:
    """统一比率口径为小数（与 tushare 对齐）：>1 视为百分数，折算为小数。"""
    if value is None:
        return None
    return value / 100 if abs(value) > 1 else value


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
                    # 与 tushare 统一为 YYYYMMDD，避免同股跨源 end_date 格式不一致
                    "end_date": period.replace("-", ""),
                    "ann_date": None,
                    "revenue": snap.get("revenue"),
                    "net_profit": snap.get("net_profit"),
                    "gross_margin": _ratio(snap.get("gross_margin")),
                    "roe": _ratio(snap.get("roe")),
                    "eps": snap.get("eps"),
                }
            )
        return rows
