"""A 股七层数据源与 DataSourceFetchAgent 测试。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.adapters.market.tencent_provider import TencentMarketAdapter
from app.adapters.registry import get_announcement_adapter, get_financial_adapter, get_market_adapter, get_research_adapter
from app.main import app
from app.services.a_share_data_source import (
    build_report_consensus,
    list_seven_layer_capabilities,
    route_task_to_layers,
)

client = TestClient(app)


def test_seven_layer_capabilities():
    caps = list_seven_layer_capabilities()
    assert len(caps) == 7
    layers = {c["layer"] for c in caps}
    assert layers == {"market", "research", "signal", "capital", "news", "fundamental", "announcement"}
    market = next(c for c in caps if c["layer"] == "market")
    assert market["ods_ready"] is True
    assert market["ods_adapter"] == "tencent"


def test_route_task_to_layers():
    assert route_task_to_layers("valuation") == ["market", "research", "fundamental"]
    assert "signal" in route_task_to_layers("sector_scan")
    with pytest.raises(Exception):
        route_task_to_layers("unknown_task")


def test_build_report_consensus():
    reports = [
        {"predict_this_year_eps": 1.0, "predict_next_year_eps": 1.2, "predict_next_two_year_eps": 1.5},
        {"predict_this_year_eps": 2.0, "predict_next_year_eps": 2.4, "predict_next_two_year_eps": 2.8},
    ]
    consensus = build_report_consensus(reports)
    assert consensus["this_year"]["count"] == 2
    assert consensus["this_year"]["avg"] == 1.5


def test_tencent_market_adapter(monkeypatch):
    fake_quotes = {
        "600519": {
            "name": "贵州茅台",
            "price": 1700.0,
            "mcap_yi": 21000.0,
        }
    }

    monkeypatch.setattr(
        "app.adapters.market.tencent_provider.fetch_tencent_quotes",
        lambda codes: fake_quotes,
    )
    adapter = TencentMarketAdapter()
    rows = adapter.fetch_market_daily(["600519"])
    assert rows[0]["stock_code"] == "600519"
    assert rows[0]["close_price"] == 1700.0


def test_registry_direct_adapters():
    assert get_market_adapter("tencent").name == "tencent"
    assert get_research_adapter("eastmoney").name == "eastmoney"
    assert get_announcement_adapter("cninfo_direct").name == "cninfo_direct"
    assert get_financial_adapter("sina").name == "sina"


def test_seven_layer_api():
    caps = client.get("/api/v1/data/seven-layer/capabilities")
    assert caps.status_code == 200
    assert caps.json()["layer_count"] == 7

    route = client.get("/api/v1/data/seven-layer/route/sector_scan")
    assert route.status_code == 200
    assert "signal" in route.json()["layers"]

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert "seven_layer" in health.json()["components"]


def test_data_source_agent_run(monkeypatch):
    monkeypatch.setattr(
        "app.agents.data_source_agent.tool_fetch_layer_preview",
        lambda layer, stock_code=None, limit=20: {"layer": layer, "mock": True},
    )
    monkeypatch.setattr(
        "app.agents.data_source_agent.tool_route_task",
        lambda task: {"task": task, "layers": route_task_to_layers(task), "capabilities": []},
    )
    resp = client.post(
        "/api/v1/agents/data-source-fetch/run",
        json={"task": "news", "limit": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_key"] == "data_source_fetch"
    assert body["agent_class"] == "B"
    assert "news" in body["fetched"]


def test_fetch_layer_news_mock(monkeypatch):
    monkeypatch.setattr(
        "app.services.a_share_data_source.fetch_eastmoney_global_news",
        lambda page_size=20: [{"title": "test", "summary": "s", "time": "2026-06-27"}],
    )
    resp = client.post(
        "/api/v1/data/seven-layer/fetch",
        json={"layer": "news", "limit": 5},
    )
    assert resp.status_code == 200
    assert "global_news" in resp.json()


def test_sync_layer_to_ods_mock(monkeypatch):
    monkeypatch.setattr(
        "app.services.ods_service.sync_market_daily",
        lambda codes, adapter_name=None: {"status": "ok", "adapter": adapter_name, "count": 1},
    )
    resp = client.post(
        "/api/v1/data/seven-layer/sync",
        json={"layer": "market", "sector_id": "sector_ai_compute"},
    )
    assert resp.status_code == 200
    assert resp.json()["adapter"] == "tencent"


def test_data_source_pipeline_presets():
    resp = client.get("/api/v1/agents/data-source-pipeline/presets")
    assert resp.status_code == 200
    presets = {p["preset"] for p in resp.json()["items"]}
    assert "full_collection" in presets
    assert "orchestrator_data_collection" in presets


def test_data_source_pipeline_run(monkeypatch):
    monkeypatch.setattr(
        "app.agents.data_source_pipeline.run_data_source_agent",
        lambda **kwargs: {"task": kwargs.get("task"), "errors": {}, "agent_summary": "ok"},
    )
    monkeypatch.setattr(
        "app.agents.data_source_pipeline.sync_all_ods_layers",
        lambda sector_id: {"status": "skipped", "sector_id": sector_id, "layers_synced": 0},
    )
    resp = client.post(
        "/api/v1/agents/data-source-pipeline/run",
        json={"sector_id": "sector_ai_compute", "preset": "full_collection"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_key"] == "data_source_pipeline"
    assert body["steps_completed"] >= 1


def test_orchestrator_data_collection_steps(monkeypatch):
    monkeypatch.setattr(
        "app.agents.orchestrator.run_data_source_agent",
        lambda **kwargs: {"status": "ok", "task": kwargs.get("task"), "errors": {}},
    )
    monkeypatch.setattr(
        "app.agents.orchestrator.sync_all_ods_layers",
        lambda sector_id: {"status": "skipped", "sector_id": sector_id},
    )
    monkeypatch.setattr(
        "app.agents.orchestrator.bootstrap_sector",
        lambda sector_id, **kwargs: {"sector_id": sector_id, "constituents": {"status": "skipped"}},
    )
    resp = client.post(
        "/api/v1/agents/orchestrator/run",
        json={
            "sector_id": "sector_ai_compute",
            "steps": ["sector_bootstrap", "data_source_fetch", "data_source_ods_sync"],
            "data_task": "sector_scan",
        },
    )
    assert resp.status_code == 200
    steps = [r["step"] for r in resp.json()["results"]]
    assert steps == ["sector_bootstrap", "data_source_fetch", "data_source_ods_sync"]
