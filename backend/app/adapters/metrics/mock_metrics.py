"""Mock 产业指标适配器 — 从 seed_metrics.json 读取。"""

from __future__ import annotations

import json
from pathlib import Path

METRICS_SEED = Path(__file__).resolve().parents[2] / "data" / "seed_metrics.json"


class MockMetricsAdapter:
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
