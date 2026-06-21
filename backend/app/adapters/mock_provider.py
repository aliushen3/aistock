"""Mock 数据适配器 — 从种子文件提供指标/行情，供开发与测试。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.services.graph_store import get_store

METRICS_SEED = Path(__file__).resolve().parents[1] / "data" / "seed_metrics.json"


class MockDataAdapter:
    name = "mock"

    def fetch_industry_metrics(self, sector_id: str) -> list[dict]:
        if not METRICS_SEED.exists():
            return []
        with open(METRICS_SEED, encoding="utf-8") as f:
            seed = json.load(f)
        if seed.get("sector_id") != sector_id:
            return []
        return [
            {
                "sector_id": sector_id,
                "product_id": m.get("product_id"),
                "metric_key": m["metric_key"],
                "period": m["period"],
                "value": m["value"],
                "unit": m.get("unit", ""),
            }
            for m in seed.get("metrics", [])
        ]

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

    def fetch_announcements(self, stock_codes: list[str], limit: int = 20) -> list[dict]:
        return []
