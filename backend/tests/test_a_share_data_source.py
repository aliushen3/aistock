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


def test_request_retry_recovers(monkeypatch):
    """卡点3：连接异常时重试恢复。"""
    from app.services import a_share_data_source as ds

    calls = {"n": 0}

    class _Resp:
        status_code = 200

    class _Client:
        def request(self, method, url, **kwargs):
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("connection reset")
            return _Resp()

    monkeypatch.setattr(ds, "_http_client", lambda: _Client())
    monkeypatch.setattr(ds.time, "sleep", lambda *a, **k: None)
    resp = ds._get("http://example.com", label="t")
    assert resp.status_code == 200
    assert calls["n"] == 2


def test_request_retry_exhausts_on_status(monkeypatch):
    """卡点3：可重试状态码（403）耗尽后抛错。"""
    from app.services import a_share_data_source as ds

    class _Resp:
        status_code = 403

    class _Client:
        def request(self, method, url, **kwargs):
            return _Resp()

    monkeypatch.setattr(ds, "_http_client", lambda: _Client())
    monkeypatch.setattr(ds.time, "sleep", lambda *a, **k: None)
    with pytest.raises(Exception):
        ds._get("http://example.com", label="t")


def test_cold_start_industry_signals(monkeypatch):
    """卡点2：冷启动信号工具聚合行业排名 + 热点。"""
    from app.agents import sector_agent_tools as st

    monkeypatch.setattr(
        "app.services.a_share_data_source.fetch_industry_comparison",
        lambda top_n=8: {"top": [{"name": "光模块", "change_pct": 5.2, "leader": "中际旭创"}]},
    )
    monkeypatch.setattr(
        "app.services.a_share_data_source.fetch_ths_hot_reason",
        lambda: [{"name": "天孚通信", "reason": "CPO+光模块", "change_pct": 10.0}],
    )
    out = st.tool_cold_start_industry_signals(top_n=5)
    assert out["industry_ranking"][0]["name"] == "光模块"
    assert out["hot_themes"][0]["reason"] == "CPO+光模块"


def test_cold_start_industry_signals_degrades(monkeypatch):
    """卡点2：信号源失败时安全降级为空，不抛错。"""
    from app.agents import sector_agent_tools as st

    def _boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr("app.services.a_share_data_source.fetch_industry_comparison", _boom)
    monkeypatch.setattr("app.services.a_share_data_source.fetch_ths_hot_reason", _boom)
    out = st.tool_cold_start_industry_signals()
    assert out == {"industry_ranking": [], "hot_themes": []}


def test_cold_start_recommendations():
    """卡点2：空图证据缺失时用行业轮动生成待验证候选。"""
    from app.agents.sector_recommend_agent import _cold_start_recommendations

    context = {
        "cold_start_signals": {
            "industry_ranking": [
                {"name": "光模块", "change_pct": 5.2, "leader": "中际旭创"},
                {"name": "CPO", "change_pct": 4.1, "leader": "天孚通信"},
            ],
            "hot_themes": [{"name": "天孚", "reason": "CPO放量", "change_pct": 9}],
        }
    }
    recs = _cold_start_recommendations(context, max_items=3)
    assert recs[0]["sector_name"] == "光模块"
    assert recs[0]["is_new"] is True
    assert recs[0]["beta_score"] == 0.35


def test_sync_all_ods_layers(monkeypatch):
    """卡点1：七层 ODS 全层同步覆盖四个就绪层。"""
    from app.services import ods_service

    monkeypatch.setattr(
        ods_service,
        "sync_layer_to_ods",
        lambda layer, sector_id: {"status": "skipped", "layer": layer},
    )
    out = ods_service.sync_all_ods_layers("sector_ai_compute")
    assert out["sector_id"] == "sector_ai_compute"
    assert set(out["results"].keys()) == {"market", "research", "fundamental", "announcement"}
