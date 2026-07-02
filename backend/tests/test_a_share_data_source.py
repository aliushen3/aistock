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


def test_fetch_industry_fund_flow(monkeypatch):
    """行业板块资金流榜：按周期映射字段并解析涨幅/主力净额。"""
    import app.services.a_share_data_source as ds

    captured: dict = {}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": {
                    "diff": [
                        {"f12": "BK0448", "f14": "光模块", "f109": 12.5, "f164": 3.2e8, "f165": 4.1},
                        {"f12": "BK0447", "f14": "CPO", "f109": 8.1, "f164": 1.1e8, "f165": 2.0},
                    ]
                }
            }

    def _fake_em_get(url, params=None, headers=None):
        captured["params"] = params
        return _Resp()

    monkeypatch.setattr(ds, "_em_get", _fake_em_get)
    rows = ds.fetch_industry_fund_flow(period="5d", top_n=10)
    assert captured["params"]["fid"] == "f164"
    assert "f109" in captured["params"]["fields"]
    assert rows[0] == {
        "code": "BK0448",
        "name": "光模块",
        "change_pct": 12.5,
        "main_net_inflow": 3.2e8,
        "main_net_pct": 4.1,
    }


def test_fetch_industry_fund_flow_dedup_tiers(monkeypatch):
    """东财多级板块（证券Ⅱ/证券Ⅲ 数值相同）应按数值签名去重。"""
    import app.services.a_share_data_source as ds

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": {
                    "diff": [
                        {"f12": "BK1366", "f14": "证券Ⅲ", "f109": 4.26, "f164": 8.3e9, "f165": 2.29},
                        {"f12": "BK0473", "f14": "证券Ⅱ", "f109": 4.26, "f164": 8.3e9, "f165": 2.29},
                        {"f12": "BK1339", "f14": "被动元件", "f109": 5.04, "f164": 5.6e9, "f165": 2.09},
                    ]
                }
            }

    monkeypatch.setattr(ds, "_em_get", lambda url, params=None, headers=None: _Resp())
    rows = ds.fetch_industry_fund_flow(period="5d", top_n=10)
    names = [r["name"] for r in rows]
    assert names == ["证券Ⅲ", "被动元件"]  # 证券Ⅱ 因数值签名重复被去重


def test_rank_industry_boards_composite(monkeypatch):
    """综合排序：多日涨幅+资金净流入归一化，命中题材加权后重排序。"""
    import app.services.a_share_data_source as ds

    boards = [
        {"code": "BK1", "name": "航空机场", "change_pct": 2.0, "main_net_inflow": 1.0e8, "main_net_pct": 1.0},
        {"code": "BK2", "name": "光模块", "change_pct": 10.0, "main_net_inflow": 5.0e8, "main_net_pct": 5.0},
    ]
    monkeypatch.setattr(ds, "fetch_industry_fund_flow", lambda period="5d", top_n=100: boards)
    monkeypatch.setattr(
        ds,
        "fetch_ths_hot_reason",
        lambda: [{"name": "中际旭创", "reason": "光模块+CPO放量", "change_pct": 10.0}],
    )
    out = ds.rank_industry_boards(top_n=5)
    assert out["period"] == "5d"
    ranking = out["ranking"]
    # 光模块涨幅/资金双高且命中题材热度，应排第一
    assert ranking[0]["name"] == "光模块"
    assert ranking[0]["theme_hits"] >= 1
    assert ranking[0]["theme_boosted"] is True
    assert ranking[0]["composite_score"] > ranking[1]["composite_score"]
    assert ranking[0]["rank"] == 1


def test_rank_industry_boards_degrades(monkeypatch):
    """资金流榜失败时安全降级为空 ranking，不抛错。"""
    import app.services.a_share_data_source as ds

    def _boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(ds, "fetch_industry_fund_flow", _boom)
    monkeypatch.setattr(ds, "fetch_ths_hot_reason", _boom)
    out = ds.rank_industry_boards(top_n=5)
    assert out["ranking"] == []


def test_cold_start_industry_signals(monkeypatch):
    """卡点2：冷启动信号工具走综合排序，输出 ranking + 热点。"""
    from app.agents import sector_agent_tools as st

    monkeypatch.setattr(
        "app.services.a_share_data_source.rank_industry_boards",
        lambda top_n=8: {
            "period": "5d",
            "ranking": [{"name": "光模块", "change_pct": 5.2, "composite_score": 0.9, "theme_hits": 2}],
            "hot_themes": [{"name": "天孚通信", "reason": "CPO+光模块", "change_pct": 10.0}],
            "weights": {"momentum": 0.4, "capital": 0.35, "theme": 0.25},
        },
    )
    out = st.tool_cold_start_industry_signals(top_n=5)
    assert out["industry_ranking"][0]["name"] == "光模块"
    assert out["hot_themes"][0]["reason"] == "CPO+光模块"
    assert out["ranking_period"] == "5d"


def test_cold_start_industry_signals_degrades(monkeypatch):
    """卡点2：信号源失败时安全降级为空，不抛错。"""
    from app.agents import sector_agent_tools as st

    def _boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr("app.services.a_share_data_source.rank_industry_boards", _boom)
    out = st.tool_cold_start_industry_signals()
    assert out == {"industry_ranking": [], "hot_themes": []}


def test_cold_start_recommendations():
    """卡点2：综合排序结果生成候选，beta_score 随综合分/题材命中动态给分。"""
    from app.agents.sector_recommend_agent import _cold_start_recommendations

    context = {
        "cold_start_signals": {
            "ranking_period": "5d",
            "industry_ranking": [
                {
                    "name": "光模块",
                    "change_pct": 10.5,
                    "main_net_inflow": 5.0e8,
                    "theme_hits": 2,
                    "composite_score": 0.95,
                },
                {
                    "name": "CPO",
                    "change_pct": 4.1,
                    "main_net_inflow": 1.0e8,
                    "theme_hits": 0,
                    "composite_score": 0.3,
                },
            ],
            "hot_themes": [{"name": "天孚", "reason": "CPO放量", "change_pct": 9}],
        }
    }
    recs = _cold_start_recommendations(context, max_items=3)
    assert recs[0]["sector_name"] == "光模块"
    assert recs[0]["is_new"] is True
    # 综合分 0.95 + 命中题材 → 0.3 + 0.3*0.95 + 0.05 = 0.635，封顶 0.6
    assert recs[0]["beta_score"] == 0.6
    assert recs[0]["signals"]["composite_score"] == 0.95
    assert recs[0]["signals"]["capex_positive"] is True
    assert recs[0]["signals"]["research_support_count"] == 2
    # 未命中题材、综合分低的候选，beta_score 更低
    assert recs[1]["beta_score"] == round(0.3 + 0.3 * 0.3, 2)


def test_rule_recommend_force_cold_start_with_existing_sector(monkeypatch):
    """强制冷启动：即使已有赛道，也走综合排序产出候选（修复 existing 限制 bug）。"""
    from app.agents import sector_recommend_agent as sra

    monkeypatch.setattr(
        "app.agents.sector_agent_tools.tool_cold_start_industry_signals",
        lambda top_n=8: {
            "ranking_period": "5d",
            "industry_ranking": [
                {"name": "半导体设备", "change_pct": 18.0, "main_net_inflow": 4.6e9, "theme_hits": 1, "composite_score": 0.92},
            ],
            "hot_themes": [{"name": "北方华创", "reason": "半导体设备国产替代", "change_pct": 8}],
        },
    )
    # 已有赛道且规则能产出候选（指标达标）：普通模式用规则结果，force 模式改走综合排序
    def _ctx() -> dict:
        return {
            "existing_sectors": [{"id": "sector_util", "name": "公用事业", "status": "beta_candidate", "human_confirmed": False}],
            "metrics_signals": [{"sector_id": "sector_util", "sector_demand_growth": 0.25, "sector_capex_yoy": 0.1}],
            "evidence_hits": [],
            "beta_criteria": {"demand_growth_threshold": 0.20},
            "watchlist": [{"sector_name": "公用事业", "sector_id": "sector_util", "keywords": ["公用事业"], "source": "ontology"}],
            "report_themes": {"themes": []},
        }

    normal = sra._rule_recommend(_ctx(), max_items=5, force_cold_start=False)
    assert normal["agent_mode"] == "rule_v1"
    assert normal["recommendations"][0]["sector_name"] == "公用事业"

    forced = sra._rule_recommend(_ctx(), max_items=5, force_cold_start=True)
    assert forced["agent_mode"] == "cold_start_v1"
    # 强制模式：综合排序候选置顶，原规则候选去重保留
    assert forced["recommendations"][0]["sector_name"] == "半导体设备"
    assert any(r["sector_name"] == "公用事业" for r in forced["recommendations"])


def test_watchlist_needs_cold_start():
    from app.agents.sector_agent_tools import watchlist_needs_cold_start

    assert watchlist_needs_cold_start([]) is True
    assert watchlist_needs_cold_start([{"source": "focus", "sector_name": "AI算力"}]) is True
    assert (
        watchlist_needs_cold_start(
            [{"source": "focus", "sector_name": "AI算力", "evidence_refs": [{"ref_id": "x"}]}]
        )
        is False
    )
    assert watchlist_needs_cold_start([{"source": "ontology", "sector_name": "算力"}]) is False


def test_sector_recommend_focus_only_empty_graph(monkeypatch):
    """空图 + 仅 focus 观察项：应产出关注方向提案或冷启动行业候选。"""
    from app.agents.sector_recommend_agent import run_sector_recommend_agent
    from app.ontology import pg_store

    monkeypatch.setattr(pg_store, "is_db_enabled", lambda: False)
    monkeypatch.setattr(
        "app.agents.sector_agent_tools.tool_list_sectors",
        lambda: [],
    )
    monkeypatch.setattr(
        "app.agents.sector_agent_tools.tool_collect_metrics_signals",
        lambda sector_id=None: [],
    )
    monkeypatch.setattr(
        "app.agents.sector_agent_tools.tool_search_research_evidence",
        lambda query, sector_id=None, top_k=10: [],
    )
    monkeypatch.setattr(
        "app.agents.sector_agent_tools.build_dynamic_watchlist",
        lambda focus=None, refresh=False: {
            "watchlist": [
                {
                    "sector_name": focus or "AI算力",
                    "sector_id": None,
                    "keywords": [focus or "AI算力"],
                    "source": "focus",
                    "terminal_products": [],
                }
            ],
            "watchlist_count": 1,
            "source_counts": {"focus": 1},
            "report_themes": {"themes": [], "uploaded_doc_count": 0, "snippet_count": 0, "extraction_mode": "rule"},
        },
    )
    monkeypatch.setattr(
        "app.agents.sector_agent_tools.tool_cold_start_industry_signals",
        lambda top_n=8: {
            "industry_ranking": [{"name": "元件", "change_pct": 3.1, "leader": "600183"}],
            "hot_themes": [],
        },
    )
    monkeypatch.setattr("app.agents.sector_recommend_agent.is_llm_enabled", lambda: False)

    out = run_sector_recommend_agent(focus="AI算力", max_recommendations=3)
    names = {r["sector_name"] for r in out["recommendations"]}
    assert "AI算力" in names or "元件" in names
    assert len(out["recommendations"]) >= 1


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


def test_sector_company_codes_empty():
    from app.services.graph_store import sector_company_codes

    assert sector_company_codes("sector_does_not_exist") == []


def test_sync_reports_no_constituents_returns_400(monkeypatch):
    class FakeStore:
        def get_sector(self, sid):
            return {"id": sid, "name": "氟化工"}

        def list_products(self, sid):
            return [{"id": "prod_hf", "name": "氢氟酸"}]

    monkeypatch.setattr("app.api.data.get_store", lambda: FakeStore())
    monkeypatch.setattr("app.api.data.sector_company_codes", lambda sid: [])

    r = client.post("/api/v1/data/sync/reports/sector_bc1ab66f")
    assert r.status_code == 400
    assert "0 只成分股" in r.json()["detail"]


def test_sync_reports_no_products_returns_400(monkeypatch):
    class FakeStore:
        def get_sector(self, sid):
            return {"id": sid, "name": "氟化工"}

        def list_products(self, sid):
            return []

    monkeypatch.setattr("app.api.data.get_store", lambda: FakeStore())
    monkeypatch.setattr("app.api.data.sector_company_codes", lambda sid: [])

    r = client.post("/api/v1/data/sync/reports/sector_bc1ab66f")
    assert r.status_code == 400
    assert "知识抽取" in r.json()["detail"]
