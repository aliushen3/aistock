"""适配器注册表。"""

from __future__ import annotations

from app.adapters.cninfo_provider import CninfoDataAdapter
from app.adapters.mock_provider import MockDataAdapter
from app.adapters.wind_provider import WindDataAdapter
from app.config import DATA_ADAPTER

_adapters = {
    "mock": MockDataAdapter(),
    "wind": WindDataAdapter(),
    "cninfo": CninfoDataAdapter(),
}


def get_adapter(name: str | None = None):
    key = (name or DATA_ADAPTER).lower()
    adapter = _adapters.get(key)
    if adapter is None:
        raise ValueError(f"未知数据适配器: {key}，可用: {list(_adapters.keys())}")
    return adapter


def list_adapters() -> list[dict]:
    from app.config import CNINFO_API_URL, DATA_ADAPTER, WIND_API_KEY, WIND_API_URL

    items = []
    for adapter in _adapters.values():
        mode = getattr(adapter, "mode", "default")
        detail: dict = {"name": adapter.name, "mode": mode}
        if adapter.name == "wind":
            detail["live_configured"] = bool(WIND_API_KEY)
            detail["gateway_url"] = WIND_API_URL
        if adapter.name == "cninfo":
            detail["live_configured"] = bool(CNINFO_API_URL)
            detail["gateway_url"] = CNINFO_API_URL or None
        items.append(detail)
    return items
