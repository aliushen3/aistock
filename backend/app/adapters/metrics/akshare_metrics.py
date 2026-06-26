"""AkShare 材料行情适配器 — 期货主力连续（futures_main_sina，免费）。

把大宗材料映射到期货主力合约，产出 material_price / price_yoy，写入
ods_industry_metric。映射表见 app/data/material_contracts.json，按 sector
配置，扩展无需改代码。AI 算力上游材料无公开期货，对应 sector 留空（宁缺毋造）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from app.adapters.market._net import ensure_ipv4, with_retry

logger = logging.getLogger(__name__)

_CONTRACTS_FILE = Path(__file__).resolve().parents[2] / "data" / "material_contracts.json"


def _load_contracts() -> dict:
    if not _CONTRACTS_FILE.exists():
        return {}
    with open(_CONTRACTS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _load_akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("未安装 akshare，请 pip install akshare") from exc
    return ak


def _to_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_rows(df) -> list[tuple[datetime, float]]:
    """归一为 [(日期, 收盘价)] 升序，过滤无效值。"""
    if df is None or getattr(df, "empty", True):
        return []
    date_col = next((c for c in ("日期", "date", "trade_date") if c in df.columns), None)
    close_col = next((c for c in ("收盘价", "close", "收盘") if c in df.columns), None)
    if not date_col or not close_col:
        return []
    out: list[tuple[datetime, float]] = []
    for _, r in df.iterrows():
        close = _to_float(r.get(close_col))
        if close is None or close <= 0:
            continue
        try:
            dt = r.get(date_col)
            dt = dt if isinstance(dt, datetime) else datetime.fromisoformat(str(dt)[:10])
        except (TypeError, ValueError):
            continue
        out.append((dt, close))
    out.sort(key=lambda x: x[0])
    return out


def _yoy(series: list[tuple[datetime, float]]) -> float | None:
    """用最近一年前最接近的交易日计算同比。"""
    if len(series) < 2:
        return None
    latest_dt, latest_close = series[-1]
    target = latest_dt - timedelta(days=365)
    prior = [(dt, c) for dt, c in series if dt <= target]
    if not prior:
        return None
    _, base_close = prior[-1]
    if base_close <= 0:
        return None
    return round(latest_close / base_close - 1, 4)


def _fetch_contract(contract: str) -> dict | None:
    ak = _load_akshare()
    ensure_ipv4()
    end = datetime.now()
    start = end - timedelta(days=420)
    df = with_retry(
        lambda: ak.futures_main_sina(
            symbol=contract,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        ),
        label=f"futures {contract}",
    )
    series = _parse_rows(df)
    if not series:
        return None
    latest_dt, latest_close = series[-1]
    return {
        "trade_date": latest_dt.strftime("%Y-%m-%d"),
        "price": latest_close,
        "yoy": _yoy(series),
    }


def fetch_material_metrics(sector_id: str) -> list[dict]:
    """可被测试 monkeypatch 的核心抓取逻辑。"""
    contracts = _load_contracts().get(sector_id, {})
    rows: list[dict] = []
    for material_key, contract in contracts.items():
        try:
            data = _fetch_contract(contract)
        except Exception as exc:
            logger.warning("材料行情拉取 %s(%s) 失败: %s", material_key, contract, exc)
            continue
        if not data:
            continue
        rows.append(
            {
                "sector_id": sector_id,
                "product_id": material_key,
                "metric_key": "material_price",
                "period": data["trade_date"],
                "value": data["price"],
                "unit": "CNY",
            }
        )
        if data["yoy"] is not None:
            rows.append(
                {
                    "sector_id": sector_id,
                    "product_id": material_key,
                    "metric_key": "price_yoy",
                    "period": data["trade_date"],
                    "value": data["yoy"],
                    "unit": "ratio",
                }
            )
    return rows


class AkshareMetricsAdapter:
    name = "akshare"

    def __init__(self) -> None:
        try:
            _load_akshare()
            self.mode = "live"
        except RuntimeError:
            self.mode = "stub"

    def fetch_industry_metrics(self, sector_id: str) -> list[dict]:
        return fetch_material_metrics(sector_id)
