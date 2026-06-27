"""Ontology 运行时测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ontology.action_executor import ActionError, action_executor
from app.ontology.object_store import get_candidate_entry, make_candidate_entry_id
from app.services.candidate_pool import clear_pool_state
from app.ontology.property_overlays import clear_all
from app.services.candidate_pool import build_pool
from app.services.graph_store import get_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    from app.config import LOAD_DEMO_SEED
    from app.db.session import init_db
    from app.ontology.property_overlays import set_product_property, set_sector_property
    from app.services.bearcase_store import clear_bear_state
    from app.services.graph_store import invalidate_store_cache
    from tests.seed_reset import reload_demo_seed

    clear_all()
    clear_pool_state()
    clear_bear_state()
    if LOAD_DEMO_SEED and init_db():
        reload_demo_seed()
    else:
        invalidate_store_cache()
    clear_pool_state()
    clear_bear_state()
    set_sector_property("sector_ai_compute", "status", "beta_confirmed")
    set_sector_property("sector_ai_compute", "human_confirmed", True)
    set_product_property("prod_cowos", "bottleneck_status", "bottleneck_confirmed")
    set_product_property("prod_low_dk_glass", "serenity_niche_confirmed", True)
    yield
    invalidate_store_cache()
    clear_all()
    clear_pool_state()
    clear_bear_state()


def test_registry_action_types():
    r = client.get("/api/v1/ontology/registry/action-types")
    assert r.status_code == 200
    names = [x["name"] for x in r.json()["items"]]
    assert "ApprovePoolEntry" in names
    assert "RejectPoolEntry" in names


def test_approve_pool_entry():
    sector_id = "sector_ai_compute"
    store = get_store()
    pool = build_pool(store, sector_id, "fusion")
    assert len(pool) > 0
    code = pool[0]["stock_code"]
    entry_id = make_candidate_entry_id(sector_id, "fusion", code)

    first = action_executor.execute_with_params(
        action_type="ApprovePoolEntry",
        target_type="CandidatePoolEntry",
        target_id=entry_id,
        params={"reason": "双逻辑共振，逻辑成立"},
        operator="analyst",
    )
    assert first.status == "pending_review"
    assert first.pending_id is not None

    result = action_executor.execute_with_params(
        action_type="ApprovePoolEntry",
        target_type="CandidatePoolEntry",
        target_id=entry_id,
        params={"reason": "双逻辑共振，逻辑成立"},
        operator="fund_manager",
    )
    assert result.audit_id is not None
    entry = get_candidate_entry(entry_id)
    assert entry["status"] == "confirmed"


def test_approve_requires_reason_length():
    sector_id = "sector_ai_compute"
    code = build_pool(get_store(), sector_id, "fusion")[0]["stock_code"]
    entry_id = make_candidate_entry_id(sector_id, "fusion", code)
    with pytest.raises(ActionError) as exc:
        action_executor.execute_with_params(
            action_type="ApprovePoolEntry",
            target_type="CandidatePoolEntry",
            target_id=entry_id,
            params={"reason": "太短"},
            operator="analyst",
        )
    assert exc.value.code == "invalid_params"


def test_candidates_confirm_via_ontology():
    sector_id = "sector_ai_compute"
    pool = build_pool(get_store(), sector_id, "fusion")
    code = pool[0]["stock_code"]
    r1 = client.post(
        "/api/v1/candidates/confirm",
        json={
            "sector_id": sector_id,
            "mode": "fusion",
            "stock_codes": [code],
            "action": "confirmed",
            "reason": "通过 Ontology Action 入池测试",
            "operator": "analyst",
        },
    )
    assert r1.status_code == 200
    assert r1.json().get("message", "").find("待") >= 0 or r1.json().get("processed", 0) >= 0

    r = client.post(
        "/api/v1/candidates/confirm",
        json={
            "sector_id": sector_id,
            "mode": "fusion",
            "stock_codes": [code],
            "action": "confirmed",
            "reason": "第二人复核通过入池",
            "operator": "fund_manager",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ontology_action"] == "ApprovePoolEntry"
    assert data["processed"] == 1


def test_invoke_calc_bottleneck_hint():
    r = client.post(
        "/api/v1/ontology/functions/calcBottleneckHint/invoke",
        json={"inputs": {"product_id": "prod_cowos"}},
    )
    assert r.status_code == 200
    out = r.json()["output"]
    assert out["product_id"] == "prod_cowos"
    assert "hint_score" in out
    assert "disclaimer" in r.json()


def test_object_set_pending_candidates():
    r = client.get(
        "/api/v1/ontology/object-sets/PendingCandidates",
        params={"sector_id": "sector_ai_compute", "mode": "fusion"},
    )
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_confirm_bottleneck_action():
    from app.ontology.property_overlays import set_product_property

    product_id = "prod_cowos"
    set_product_property(product_id, "bottleneck_status", "bottleneck_hint")
    action_executor.execute_with_params(
        action_type="ConfirmBottleneck",
        target_type="Product",
        target_id=product_id,
        params={"reason": "扩产周期长，供需缺口明确"},
        operator="analyst",
    )
    result = action_executor.execute_with_params(
        action_type="ConfirmBottleneck",
        target_type="Product",
        target_id=product_id,
        params={"reason": "扩产周期长，供需缺口明确"},
        operator="fund_manager",
    )
    assert result.action_type == "ConfirmBottleneck"
    from app.ontology.object_store import get_product

    product = get_product(product_id)
    assert product["bottleneck_status"] == "bottleneck_confirmed"


def test_publish_report_action():
    store = get_store()
    report = __import__("app.services.report", fromlist=["generate_report"]).generate_report(
        store, "sector_ai_compute", "fusion"
    )
    action_executor.execute_with_params(
        action_type="PublishReport",
        target_type="ResearchReport",
        target_id=report["report_id"],
        params={"comments": "逻辑链完整"},
        operator="analyst",
    )
    result = action_executor.execute_with_params(
        action_type="PublishReport",
        target_type="ResearchReport",
        target_id=report["report_id"],
        params={"comments": "逻辑链完整"},
        operator="fund_manager",
    )
    assert result.action_type == "PublishReport"
    from app.ontology.object_store import get_research_report

    published = get_research_report(report["report_id"])
    assert published is not None
    assert published["status"] == "published"


def test_graph_projector_skips_without_neo4j():
    from app.ontology.graph_projector import project_graph

    result = project_graph()
    assert result["status"] in ("ok", "skipped")


def test_seed_loader_builds_dict():
    from app.db.session import init_db
    from app.ontology import pg_store
    from app.ontology.seed_loader import build_seed_dict_from_db, is_db_seeded, load_seed_if_empty

    if not init_db():
        return
    pg_store.set_db_enabled(True)
    load_seed_if_empty()
    assert is_db_seeded()
    data = build_seed_dict_from_db()
    assert len(data["sectors"]) > 0
    assert len(data["products"]) > 0


def test_calibrate_chain_add_link():
    p1, p2 = "prod_inp_substrate", "prod_abf_film"
    try:
        action_executor.execute_with_params(
            action_type="CalibrateChain",
            target_type="Link.upstream_of",
            target_id=f"{p1}:{p2}",
            params={
                "operation": "remove",
                "source_id": p1,
                "target_id": p2,
                "reason": "测试前清理",
                "evidence_refs": [],
            },
            operator="analyst",
        )
    except ActionError:
        pass
    result = action_executor.execute_with_params(
        action_type="CalibrateChain",
        target_type="Link.upstream_of",
        target_id=f"{p1}:{p2}",
        params={
            "operation": "add",
            "source_id": p1,
            "target_id": p2,
            "reason": "测试校准产业链关系",
            "evidence_refs": ["ev-001"],
        },
        operator="analyst",
    )
    assert result.action_type == "CalibrateChain"


def test_workflow_gate_blocks_confirm_without_sector():
    from app.ontology.property_overlays import set_sector_property

    set_sector_property("sector_ai_compute", "status", "beta_candidate")
    set_sector_property("sector_ai_compute", "human_confirmed", False)
    sector_id = "sector_ai_compute"
    pool = build_pool(get_store(), sector_id, "fusion")
    code = pool[0]["stock_code"]
    r = client.post(
        "/api/v1/candidates/confirm",
        json={
            "sector_id": sector_id,
            "mode": "fusion",
            "stock_codes": [code],
            "action": "confirmed",
            "reason": "门控测试应被拦截",
            "operator": "analyst",
        },
    )
    assert r.status_code == 403


def test_graphrag_report():
    from app.services.report import generate_report

    report = generate_report(get_store(), "sector_ai_compute", "fusion")
    assert "graphrag" in report["generated_by"]
    assert report.get("rag_context") is not None


def test_knowledge_ingest():
    r = client.post(
        "/api/v1/knowledge/ingest",
        json={
            "sector_id": "sector_ai_compute",
            "source_ref": "测试研报",
            "content": "磷化铟衬底是 EML光芯片 的上游，产能紧张属于瓶颈环节。",
        },
    )
    assert r.status_code == 200
    assert r.json()["draft_id"].startswith("draft_")


def test_knowledge_upload_and_vector_search():
    from app.services.vector_store import search_documents

    content = (
        "光模块产业链分析：磷化铟衬底是 EML光芯片 的上游，"
        "产能紧张扩产周期长达24个月，属于瓶颈环节。"
    )
    r = client.post(
        "/api/v1/knowledge/upload",
        data={"sector_id": "sector_ai_compute", "source_ref": "上传测试研报", "extract_knowledge": "true"},
        files={"file": ("report.txt", content.encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["doc_id"].startswith("doc_")
    assert body["chunk_count"] >= 1
    assert body["vector_index"]["count"] >= 1

    hits = search_documents("磷化铟 瓶颈", sector_id="sector_ai_compute", top_k=3)
    assert len(hits) >= 1
    assert any("磷化铟" in (h.get("excerpt") or "") for h in hits)

    docs = client.get("/api/v1/knowledge/documents", params={"sector_id": "sector_ai_compute"})
    assert docs.status_code == 200
    assert any(d["doc_id"] == body["doc_id"] for d in docs.json()["items"])


def test_diagnosis_api():
    r = client.get("/api/v1/diagnosis/sector/sector_ai_compute")
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_alerts_api():
    r = client.get("/api/v1/alerts/sector/sector_ai_compute")
    assert r.status_code == 200
    assert "items" in r.json()


def test_dynamic_watchlist():
    r = client.get("/api/v1/agents/watchlist")
    assert r.status_code == 200
    body = r.json()
    assert body["dynamic"] is True
    assert body["watchlist_count"] >= 1
    sources = {item["source"] for item in body["watchlist"]}
    assert "base" not in sources

    ai = next((x for x in body["watchlist"] if x["sector_name"] == "AI算力"), None)
    assert ai is not None
    assert ai["sector_id"] == "sector_ai_compute"
    assert body["watchlist_count"] >= len(body.get("source_counts", {}))

    focused = client.get("/api/v1/agents/watchlist", params={"focus": "AI算力"})
    assert focused.status_code == 200
    assert focused.json()["watchlist_count"] >= 1
    assert any(x.get("source") == "focus" for x in focused.json()["watchlist"])


def test_sector_recommend_agent():
    r = client.post(
        "/api/v1/agents/sector-recommend/run",
        json={"focus": "AI算力", "query": "哪些赛道需求增速高"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == "sector_recommend_pipeline_v1"
    assert body.get("agent_class") == "B"
    assert body.get("runtime") == "pipeline"
    assert len(body["recommendations"]) >= 1
    assert "context_stats" in body
    assert "report_themes" in body["context_stats"]
    assert body["context_stats"]["watchlist_count"] >= 1
    ai = next((x for x in body["recommendations"] if x["sector_name"] == "AI算力"), None)
    assert ai is not None
    assert ai["beta_score"] > 0

    listed = client.get("/api/v1/agents/sector-recommendations", params={"status": "proposed"})
    assert listed.status_code == 200
    assert any(x["rec_id"] == ai["rec_id"] for x in listed.json()["items"])

    adopt = client.post(f"/api/v1/agents/sector-recommendations/{ai['rec_id']}/adopt")
    assert adopt.status_code == 200
    assert adopt.json()["sector_id"] == "sector_ai_compute"


def test_ods_sync_and_metrics():
    from app.services.ods_service import seed_ods_metrics_if_empty, sync_industry_metrics

    seed_ods_metrics_if_empty()
    r = client.post("/api/v1/data/sync/metrics/sector_ai_compute")
    assert r.status_code == 200
    assert r.json()["count"] >= 1

    dash = client.get("/api/v1/metrics/sector/sector_ai_compute/dashboard")
    assert dash.status_code == 200
    assert "data_source" in dash.json()["dashboard"]

    stats = client.get("/api/v1/data/ods/stats")
    assert stats.status_code == 200
    assert stats.json().get("industry_metrics", 0) >= 1 or stats.json().get("enabled") is False

    direct = sync_industry_metrics("sector_ai_compute")
    assert direct["status"] in ("ok", "skipped")


def test_typed_adapters_registry():
    from app.adapters.registry import get_adapter, get_market_adapter, list_adapters

    names = {a["name"] for a in list_adapters()}
    assert {"mock", "cninfo", "akshare", "tushare", "auto"}.issubset(names)
    assert "wind" not in names

    market_names = {a["name"] for a in list_adapters() if a.get("kind") == "market"}
    assert {"mock", "akshare", "tushare", "auto"}.issubset(market_names)

    financial_names = {a["name"] for a in list_adapters() if a.get("kind") == "financial"}
    assert {"mock", "tushare"}.issubset(financial_names)

    research_names = {a["name"] for a in list_adapters() if a.get("kind") == "research"}
    assert {"mock", "em"}.issubset(research_names)

    announcement_names = {a["name"] for a in list_adapters() if a.get("kind") == "announcement"}
    assert {"mock", "cninfo", "akshare"}.issubset(announcement_names)

    metrics_names = {a["name"] for a in list_adapters() if a.get("kind") == "metrics"}
    assert {"mock", "akshare"}.issubset(metrics_names)

    constituent_names = {a["name"] for a in list_adapters() if a.get("kind") == "constituent"}
    assert {"mock", "akshare"}.issubset(constituent_names)

    r = client.post(
        "/api/v1/data/sync/metrics/sector_ai_compute",
        params={"adapter": "mock"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "skipped")
    assert body.get("adapter") == "mock" or body.get("count", 0) >= 1

    ann = client.post(
        "/api/v1/data/sync/announcements/sector_ai_compute",
        params={"adapter": "cninfo"},
    )
    assert ann.status_code == 200
    ann_body = ann.json()
    assert ann_body["status"] in ("ok", "skipped")
    if ann_body["status"] == "ok":
        assert ann_body["adapter"] == "cninfo"

    market = get_market_adapter("mock")
    assert market.name == "mock"
    mk = market.fetch_market_daily(["AI0001"])
    assert len(mk) == 1

    composite = get_adapter("akshare")
    assert composite.name == "akshare"

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert "data_adapters" in health.json()["components"]


def test_akshare_market_adapter(monkeypatch):
    from app.adapters.market.akshare_provider import AkshareMarketAdapter

    def fake_fetch(stock_codes):
        return [
            {
                "stock_code": "600519",
                "trade_date": "2026-06-24",
                "close_price": 1700.0,
                "market_cap_billion": 21000.0,
                "pe_percentile": 0.72,
            }
        ]

    monkeypatch.setattr(
        "app.adapters.market.akshare_provider.fetch_market_rows",
        fake_fetch,
    )
    adapter = AkshareMarketAdapter()
    rows = adapter.fetch_market_daily(["600519.SH"])
    assert rows[0]["stock_code"] == "600519"
    assert rows[0]["market_cap_billion"] == 21000.0

    r = client.post(
        "/api/v1/data/sync/market/sector_ai_compute",
        params={"adapter": "akshare"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "skipped")
    if body["status"] == "ok":
        assert body["adapter"] == "akshare"


def test_tushare_market_adapter(monkeypatch):
    from app.adapters.market.tushare_provider import TushareMarketAdapter

    monkeypatch.setenv("TUSHARE_TOKEN", "test-token")

    def fake_fetch(stock_codes):
        return [
            {
                "stock_code": "000001",
                "trade_date": "2026-06-24",
                "close_price": 12.5,
                "market_cap_billion": 2400.0,
                "pe_percentile": 0.55,
            }
        ]

    monkeypatch.setattr(
        "app.adapters.market.tushare_provider.fetch_market_rows",
        fake_fetch,
    )
    adapter = TushareMarketAdapter()
    rows = adapter.fetch_market_daily(["000001.SZ"])
    assert rows[0]["stock_code"] == "000001"
    assert rows[0]["pe_percentile"] == 0.55


def test_auto_market_adapter_fallback():
    from app.adapters.market.auto_provider import AutoMarketAdapter

    sample = [
        {
            "stock_code": "600519",
            "trade_date": "2026-06-24",
            "close_price": 1700.0,
            "market_cap_billion": 21000.0,
            "pe_percentile": 0.72,
        }
    ]

    class _FailTushare:
        mode = "live"

        def fetch_market_daily(self, codes):
            raise RuntimeError("tushare down")

    class _OkAkshare:
        mode = "live"

        def fetch_market_daily(self, codes):
            return sample

    adapter = AutoMarketAdapter()
    adapter._tushare = _FailTushare()
    adapter._akshare = _OkAkshare()
    rows = adapter.fetch_market_daily(["600519.SH"])
    assert rows[0]["stock_code"] == "600519"
    assert rows[0]["market_cap_billion"] == 21000.0


def test_akshare_info_parsing(monkeypatch):
    from app.adapters.market import akshare_provider

    monkeypatch.setattr(
        akshare_provider,
        "_info_map",
        lambda code: {"最新": "7.05", "总市值": "84111501770.55"},
    )
    monkeypatch.setattr(akshare_provider, "_pe_history", lambda code: [])
    row = akshare_provider._fetch_one("000002", "2026-06-24")
    assert row["close_price"] == 7.05
    assert round(row["market_cap_billion"], 2) == 841.12
    assert row["pe_percentile"] is None


def test_announcement_classify_and_registry():
    from app.adapters.announcement.akshare_announcement import _ann_id, _classify
    from app.adapters.registry import get_announcement_adapter

    assert _classify("关于募投项目扩产的公告") == "capacity_expansion"
    assert _classify("2025年年度业绩预增公告") == "earnings"
    assert _classify("控股股东减持股份计划") == "shareholding"
    assert _classify("日常经营公告") == "general"

    a = _ann_id("003031", "12345", "标题", "2026-06-25")
    assert a == "cninfo_12345"
    b = _ann_id("003031", None, "标题", "2026-06-25")
    assert b.startswith("cninfo_003031_")

    adapter = get_announcement_adapter("akshare")
    assert adapter.name == "akshare"


def test_tushare_financial_parsing(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "test-token")
    from app.adapters.financial import tushare_financial

    monkeypatch.setattr(tushare_financial, "_load_pro", lambda: object())
    monkeypatch.setattr(
        tushare_financial,
        "_latest_indicator",
        lambda pro, ts_code: {
            "end_date": "20251231",
            "ann_date": "20260328",
            "eps": "2.15",
            "roe": "18.50",
            "grossprofit_margin": "42.30",
        },
    )
    monkeypatch.setattr(
        tushare_financial,
        "_income_for_period",
        lambda pro, ts_code, end_date: {"revenue": "1.2e10", "n_income": "1.8e9"},
    )
    rows = tushare_financial.fetch_financial_rows(["003031.SZ"])
    assert len(rows) == 1
    row = rows[0]
    assert row["end_date"] == "20251231"
    assert row["eps"] == 2.15
    assert round(row["roe"], 4) == 0.185
    assert round(row["gross_margin"], 4) == 0.423
    assert row["revenue"] == 1.2e10


def test_em_research_parsing(monkeypatch):
    from app.adapters.research import em_research

    class _FakeRow(dict):
        def get(self, k, default=None):
            return dict.get(self, k, default)

    class _FakeDF:
        empty = False

        def iterrows(self):
            yield 0, _FakeRow(
                {"报告名称": "深度研报", "报告日期": "2026-06-20", "机构": "某券商", "东财评级": "买入"}
            )

    monkeypatch.setattr(em_research, "_load_akshare", lambda: object())
    monkeypatch.setattr(em_research, "ensure_ipv4", lambda: None)
    monkeypatch.setattr(em_research, "with_retry", lambda fn, label="": _FakeDF())
    rows = em_research._fetch_one("003031", 20)
    assert len(rows) == 1
    assert rows[0]["title"] == "深度研报"
    assert rows[0]["org_name"] == "某券商"
    assert rows[0]["rating"] == "买入"
    assert rows[0]["report_date"] == "2026-06-20"
    assert rows[0]["report_key"].startswith("em_003031_")


def test_akshare_metrics_adapter(monkeypatch):
    from app.adapters.metrics import akshare_metrics

    monkeypatch.setattr(
        akshare_metrics, "_load_contracts", lambda: {"sector_test": {"mat_x": "LC0"}}
    )
    monkeypatch.setattr(
        akshare_metrics,
        "_fetch_contract",
        lambda contract: {"trade_date": "2026-06-25", "price": 95000.0, "yoy": -0.32},
    )
    rows = akshare_metrics.fetch_material_metrics("sector_test")
    assert len(rows) == 2
    price_row = next(r for r in rows if r["metric_key"] == "material_price")
    yoy_row = next(r for r in rows if r["metric_key"] == "price_yoy")
    assert price_row["value"] == 95000.0
    assert price_row["product_id"] == "mat_x"
    assert price_row["period"] == "2026-06-25"
    assert price_row["unit"] == "CNY"
    assert yoy_row["value"] == -0.32

    assert akshare_metrics.fetch_material_metrics("sector_unmapped") == []


def test_akshare_metrics_yoy():
    from datetime import datetime

    from app.adapters.metrics import akshare_metrics

    series = [
        (datetime(2025, 6, 20), 100.0),
        (datetime(2025, 12, 20), 120.0),
        (datetime(2026, 6, 25), 150.0),
    ]
    assert akshare_metrics._yoy(series) == 0.5
    assert akshare_metrics._yoy([(datetime(2026, 6, 25), 150.0)]) is None


def test_dashboard_material_metrics_bucket(monkeypatch):
    from app.services import metrics as metrics_service

    monkeypatch.setattr(
        metrics_service,
        "list_sector_metrics",
        lambda sector_id: [
            {
                "sector_id": sector_id,
                "product_id": None,
                "product_name": None,
                "metric_key": "sector_demand_growth",
                "metric_label": "需求增速",
                "period": "2026Q1",
                "value": 0.35,
                "unit": "ratio",
                "data_source": "ods",
            },
            {
                "sector_id": sector_id,
                "product_id": "mat_lithium_carbonate",
                "product_name": None,
                "metric_key": "material_price",
                "metric_label": "材料现价",
                "period": "2026-06-25",
                "value": 95000.0,
                "unit": "CNY",
                "data_source": "akshare",
            },
            {
                "sector_id": sector_id,
                "product_id": "mat_lithium_carbonate",
                "product_name": None,
                "metric_key": "price_yoy",
                "metric_label": "价格同比",
                "period": "2026-06-25",
                "value": -0.32,
                "unit": "ratio",
                "data_source": "akshare",
            },
        ],
    )
    summary = metrics_service.dashboard_summary("sector_ai_compute")
    assert "material_metrics" in summary
    assert len(summary["material_metrics"]) == 1
    mat = summary["material_metrics"][0]
    assert mat["material_key"] == "mat_lithium_carbonate"
    assert mat["price"] == 95000.0
    assert mat["price_yoy"] == -0.32
    assert mat["unit"] == "CNY"


def test_map_company_to_products():
    from app.db.models import OntProduct
    from app.services.graph_ingest import map_company_to_products

    products = [
        OntProduct(
            id="prod_optical_module",
            name="光模块",
            layer="mid",
            sector_id="sector_ai_compute",
        ),
        OntProduct(
            id="prod_hsb_pcb",
            name="高速PCB",
            layer="mid",
            sector_id="sector_ai_compute",
        ),
    ]
    config = {
        "default_product_id": "prod_optical_module",
        "product_keywords": {
            "prod_optical_module": ["中际", "光模块"],
            "prod_hsb_pcb": ["PCB", "沪电"],
        },
    }
    assert map_company_to_products("中际旭创", products, config) == ["prod_optical_module"]
    assert map_company_to_products("沪电股份", products, config) == ["prod_hsb_pcb"]
    assert map_company_to_products("未知公司", products, config) == ["prod_optical_module"]


def test_constituent_row_parsing():
    from app.adapters.constituent.akshare_constituent import _row_to_record

    rec = _row_to_record({"代码": "300308", "名称": "中际旭创", "总市值": 120000000000}, "concept", "CPO概念")
    assert rec is not None
    assert rec["stock_code"] == "300308"
    assert rec["name"] == "中际旭创"
    assert rec["market_cap_billion"] == 1200.0


def test_sync_constituents_mock(monkeypatch):
    from tests.seed_reset import reload_demo_seed
    from app.services.graph_store import get_store

    monkeypatch.setattr("app.ontology.graph_projector.project_graph", lambda: None)

    try:
        before = get_store()
        assert before.get_company("AI0001") is not None

        r = client.post(
            "/api/v1/data/sync/constituents/sector_ai_compute",
            params={"adapter": "mock"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["adapter"] == "mock"
        assert body["companies_upserted"] >= 3
        assert body["demo_removed"] >= 1

        from app.services.graph_store import invalidate_store_cache

        invalidate_store_cache()
        store = get_store()
        assert store.get_company("601138") is not None
        assert store.get_company("300308") is not None
        assert store.get_company("AI0001") is None
    finally:
        reload_demo_seed()


def test_candidate_pool_overlay_seed_fallback(monkeypatch):
    from app.services import candidate_pool

    items = [{"stock_code": "AI0001", "market_cap_billion": 2000}]
    monkeypatch.setattr(candidate_pool, "build_buy_side_pool", lambda store, sid: items)
    monkeypatch.setattr(candidate_pool, "build_serenity_pool", lambda store, sid: [])
    candidate_pool._apply_ods_overlay(items)
    assert items[0]["data_origin"] == "seed"
    assert items[0]["market_cap_billion"] == 2000


def test_candidate_pool_overlay_from_ods(monkeypatch):
    from app.services import candidate_pool, ods_service

    monkeypatch.setattr(
        ods_service,
        "latest_market_overlay",
        lambda codes: {"AI0001": {"market_cap_billion": 1800.0, "pe_percentile": 0.6, "close_price": 12.3, "trade_date": "2026-06-25", "source": "tushare"}},
    )
    monkeypatch.setattr(
        ods_service,
        "latest_financial_overlay",
        lambda codes: {"AI0001": {"gross_margin": 0.41, "roe": 0.18, "end_date": "20251231", "source": "tushare"}},
    )
    items = [{"stock_code": "AI0001", "market_cap_billion": 2000}]
    candidate_pool._apply_ods_overlay(items)
    assert items[0]["data_origin"] == "ods"
    assert items[0]["market_cap_billion"] == 1800.0
    assert items[0]["pe_percentile"] == 0.6
    assert items[0]["gross_margin"] == 0.41
    assert items[0]["market_data_date"] == "2026-06-25"


def test_report_ingest_bridge(monkeypatch):
    from app.services import report_ingest_bridge

    def fake_reports(stock_code=None, limit=50):
        if stock_code == "AI0002":
            return [{"title": "光模块产能紧张涨价", "org_name": "某券商", "rating": "买入"}]
        return []

    monkeypatch.setattr(report_ingest_bridge, "list_ods_external_reports", fake_reports)
    result = report_ingest_bridge.ingest_external_reports_to_draft("sector_ai_compute")
    assert result["status"] == "ok"
    assert result["report_lines"] >= 1
    assert result["bottleneck_hints"] >= 1
    assert result["draft_id"].startswith("draft_")

    monkeypatch.setattr(
        report_ingest_bridge, "list_ods_external_reports", lambda stock_code=None, limit=50: []
    )
    empty = report_ingest_bridge.ingest_external_reports_to_draft("sector_ai_compute")
    assert empty["status"] == "empty"
    assert empty["report_lines"] == 0


def test_knowledge_ingest_agent():
    content = "磷化铟衬底是 EML光芯片 的上游，产能紧张扩产周期长达24个月，属于瓶颈环节。"
    r = client.post(
        "/api/v1/agents/knowledge-ingest/run",
        json={
            "sector_id": "sector_ai_compute",
            "source_ref": "Agent抽取测试",
            "content": content,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == "knowledge_ingest_react_v1"
    assert body["draft_id"].startswith("draft_")
    assert len(body["extracted"].get("relations", [])) >= 1 or len(body["extracted"].get("bottleneck_hints", [])) >= 1

    listed = client.get("/api/v1/knowledge/drafts", params={"sector_id": "sector_ai_compute"})
    assert listed.status_code == 200
    assert any(d["draft_id"] == body["draft_id"] for d in listed.json()["items"])


def test_bottleneck_scout_agent():
    r = client.post(
        "/api/v1/agents/bottleneck-scout/run",
        json={"sector_id": "sector_ai_compute", "min_hint_level": "hint_medium"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == "bottleneck_scout_v1"
    assert body["scanned_products"] >= 1
    assert len(body["recommendations"]) >= 1
    assert body["recommendations"][0]["rec_id"].startswith("brec_")

    listed = client.get(
        "/api/v1/agents/bottleneck-recommendations",
        params={"sector_id": "sector_ai_compute", "status": "proposed"},
    )
    assert listed.status_code == 200
    assert len(listed.json()["items"]) >= 1


def test_orchestrator_pipeline():
    r = client.post(
        "/api/v1/agents/orchestrator/run",
        json={
            "sector_id": "sector_ai_compute",
            "focus": "AI算力",
            "steps": ["sector_recommend", "bottleneck_scout", "monitor_watch"],
            "stop_on_gate": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == "invest_research_orchestrator_v1"
    step_names = [x["step"] for x in body["results"]]
    assert step_names == ["sector_recommend", "bottleneck_scout", "monitor_watch"]
    scout = next(x for x in body["results"] if x["step"] == "bottleneck_scout")
    assert scout["status"] == "ok"


def test_serenity_path_agent():
    r = client.post(
        "/api/v1/agents/serenity-path/run",
        json={"sector_id": "sector_ai_compute", "min_serenity_hint": 40},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == "serenity_path_v1"
    assert body["path_count"] >= 0
    if body["recommendations"]:
        assert body["recommendations"][0]["rec_id"].startswith("srec_")


def test_report_graphrag_agent():
    r = client.post(
        "/api/v1/agents/report-graphrag/run",
        json={"sector_id": "sector_ai_compute", "mode": "fusion"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == "report_graphrag_v1"
    assert body["report_id"].startswith("rpt_")
    assert body["status"] == "draft"


def test_candidate_fusion_agent():
    r = client.post(
        "/api/v1/agents/candidate-fusion/run",
        json={"sector_id": "sector_ai_compute", "mode": "fusion"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == "candidate_fusion_v1"
    assert "candidate_count" in body


def test_monitor_watch_agent():
    r = client.post(
        "/api/v1/agents/monitor-watch/run",
        json={"sector_id": "sector_ai_compute"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == "monitor_watch_v1"
    assert body["alert_count"] >= 0
    assert "alerts" in body


def test_embedding_backend():
    from app.services.embedding import embed_text, embedding_dim, embedding_mode

    assert embedding_mode() == "pseudo_hash"
    assert embedding_dim() == 8
    vec = embed_text("CoWoS 先进封装 瓶颈")
    assert len(vec) == 8
    assert abs(sum(v * v for v in vec) ** 0.5 - 1.0) < 0.01

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["components"]["embedding"]["mode"] == "pseudo_hash"


def test_sector_theme_extractor():
    from app.services.sector_theme_extractor import extract_sector_themes_from_reports

    r = extract_sector_themes_from_reports(focus="AI算力")
    assert "themes" in r
    assert r["extraction_mode"] in ("rule", "llm")


def test_global_alerts_with_recommendations():
    client.post("/api/v1/agents/sector-recommend/run", json={"focus": "AI算力"})
    r = client.get("/api/v1/alerts/global")
    assert r.status_code == 200
    types = [a["type"] for a in r.json()["items"]]
    assert "sector_recommendation_pending" in types or "sector_recommendation" in types


def test_owl_validate():
    r = client.get("/api/v1/alerts/ontology/validate/sector_ai_compute")
    assert r.status_code == 200
    assert "valid" in r.json()


def test_health_components():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert "components" in r.json()


def test_hybrid_graph_store():
    store = get_store()
    assert hasattr(store, "traversal_backend")
    paths = store.reverse_paths("prod_ai_server", 1, 4)
    assert isinstance(paths, list)


def test_knowledge_async_fallback():
    r = client.post(
        "/api/v1/knowledge/ingest/async",
        json={
            "sector_id": "sector_ai_compute",
            "source_ref": "异步测试",
            "content": "磷化铟衬底是 EML光芯片 的上游，产能紧张属于瓶颈环节。",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("queued", "completed")


# ---- v3.0 三条主线：F1 反证 / F2 保鲜 / F3 三道闸 ----


def test_edge_value_functions():
    r = client.post(
        "/api/v1/ontology/functions/edgeSignal/invoke",
        json={"inputs": {"stock_code": "AI0001"}},
    )
    assert r.status_code == 200
    out = r.json()["output"]
    assert out["priced_in"] in ("low", "medium", "high", "unknown")

    rv = client.post(
        "/api/v1/ontology/functions/valueCapture/invoke",
        json={"inputs": {"product_id": "prod_cowos", "company_code": "AI0005"}},
    )
    assert rv.status_code == 200
    assert rv.json()["output"]["captures_economics"] in ("yes", "partial", "no", "unknown")

    # 缺失降级
    miss = client.post(
        "/api/v1/ontology/functions/edgeSignal/invoke",
        json={"inputs": {"stock_code": "NOPE"}},
    )
    assert miss.json()["output"]["degraded"] is True


def test_bearcase_agent_and_gate():
    from app.ontology.action_executor import ActionError, action_executor
    from app.ontology.object_store import make_candidate_entry_id

    run = client.post("/api/v1/agents/bear-case/run", json={"sector_id": "sector_ai_compute", "mode": "fusion"})
    assert run.status_code == 200
    body = run.json()
    assert body["agent"] == "bear_case_v1"
    highs = [b for b in body["bear_cases"] if b["severity"] == "high"]
    assert highs, "应至少有一条高severity空头论点"

    bear = highs[0]
    code = bear["stock_code"]
    entry_id = make_candidate_entry_id("sector_ai_compute", "fusion", code)

    # 闸三阻断：高severity空头未回应 → ApprovePoolEntry 失败
    with pytest.raises(ActionError) as exc:
        action_executor.execute_with_params(
            action_type="ApprovePoolEntry",
            target_type="CandidatePoolEntry",
            target_id=entry_id,
            params={"reason": "闸门测试应被拦截"},
            operator="analyst",
        )
    assert exc.value.code == "precondition_failed"

    # 回应该标的所有高severity空头论点
    for b in [x for x in body["bear_cases"] if x["stock_code"] == code and x["severity"] == "high"]:
        rb = client.post(
            f"/api/v1/ontology/actions/RebutBearCase/execute",
            json={
                "target": {"type": "BearCase", "id": b["bear_id"]},
                "params": {"rebuttal": "已通过长协与备选产能对冲该风险，逻辑仍成立"},
                "operator": "analyst",
            },
        )
        assert rb.status_code == 200

    # 回应后可入池（双人复核）
    first = action_executor.execute_with_params(
        "ApprovePoolEntry", "CandidatePoolEntry", entry_id, {"reason": "空头已回应，逻辑成立"}, "analyst"
    )
    assert first.status == "pending_review"
    second = action_executor.execute_with_params(
        "ApprovePoolEntry", "CandidatePoolEntry", entry_id, {"reason": "空头已回应，逻辑成立"}, "fund_manager"
    )
    assert second.audit_id is not None


def test_freshness_lifecycle():
    from datetime import datetime, timezone

    from app.ontology.action_executor import action_executor
    from app.ontology.object_store import get_product
    from app.services.freshness import product_freshness

    store = get_store()
    # prod_ccl 种子 last_verified_at=2024-01-01，half_life 90 → stale
    ccl = store.get_product("prod_ccl")
    fr = product_freshness(ccl, now=datetime(2026, 6, 21, tzinfo=timezone.utc))
    assert fr["freshness"] == "stale"

    # 瓶颈生命周期：confirmed → easing
    action_executor.execute_with_params(
        action_type="ConfirmBottleneckEasing",
        target_type="Product",
        target_id="prod_cowos",
        params={"new_status": "bottleneck_easing", "reason": "台积电扩产落地，供需缺口缓解"},
        operator="analyst",
    )
    assert get_product("prod_cowos")["bottleneck_status"] == "bottleneck_easing"


def test_object_sets_v3():
    client.post("/api/v1/agents/bear-case/run", json={"sector_id": "sector_ai_compute", "mode": "fusion"})
    ub = client.get("/api/v1/ontology/object-sets/UnrebuttedBearCases", params={"sector_id": "sector_ai_compute"})
    assert ub.status_code == 200
    assert ub.json()["count"] >= 1

    stale = client.get("/api/v1/ontology/object-sets/StaleKnowledge", params={"sector_id": "sector_ai_compute"})
    assert stale.status_code == 200
    assert any(it["id"] == "prod_ccl" for it in stale.json()["items"])

    knowledge_stale = client.get("/api/v1/knowledge/stale", params={"sector_id": "sector_ai_compute"})
    assert knowledge_stale.status_code == 200
    assert knowledge_stale.json()["count"] >= 1


def test_hint_calibration_outcome_f4():
    from app.ontology.property_overlays import set_product_property
    from app.services.hint_calibration import calibration_summary, list_outcomes

    product_id = "prod_cowos"
    set_product_property(product_id, "bottleneck_status", "bottleneck_hint")
    action_executor.execute_with_params(
        action_type="ConfirmBottleneck",
        target_type="Product",
        target_id=product_id,
        params={"reason": "扩产周期长，供需缺口明确"},
        operator="analyst",
    )
    action_executor.execute_with_params(
        action_type="ConfirmBottleneck",
        target_type="Product",
        target_id=product_id,
        params={"reason": "扩产周期长，供需缺口明确"},
        operator="fund_manager",
    )

    outcomes = list_outcomes(sector_id="sector_ai_compute")
    assert any(o["product_id"] == product_id and o["verdict"] == "confirmed" for o in outcomes)

    cal = client.get("/api/v1/metrics/hint-calibration")
    assert cal.status_code == 200
    body = cal.json()
    assert "weight_version" in body
    assert "calibration_note" in body
    assert body["confirmed_count"] >= 1

    hint = client.post(
        "/api/v1/ontology/functions/calcBottleneckHint/invoke",
        json={"inputs": {"product_id": product_id}},
    )
    assert hint.status_code == 200
    out = hint.json()["output"]
    assert "weight_version" in out
    assert "weight_breakdown" in out
    assert "calibration_note" in out


def test_source_trust_and_draft_validation_f5():
    from app.services import extraction as extraction_service
    from app.services.source_trust import detect_reflexive_narrative, validate_relation_promotion

    reflexive = detect_reflexive_narrative(
        [
            {"source_type": "research_report", "source_ref": "中信证券-AI算力深度"},
            {"source_type": "research_report", "source_ref": "中信证券-AI算力跟踪"},
        ]
    )
    assert reflexive is True

    blocked = validate_relation_promotion(
        {
            "source_id": "prod_gpu",
            "target_id": "prod_cowos",
            "confidence": "medium",
        },
        "research_report",
        "某券商-AI算力",
    )
    assert blocked["can_confirm"] is False
    assert blocked["report_only"] is True

    draft = extraction_service.ingest_document(
        "sector_ai_compute",
        "research_report",
        "测试研报",
        "磷化铟衬底是 EML光芯片 的上游，产能紧张扩产周期长达24个月，属于瓶颈环节。",
    )
    validation = client.get(f"/api/v1/knowledge/drafts/{draft['draft_id']}/validate")
    assert validation.status_code == 200
    assert validation.json()["can_confirm_all"] is False

    hard = validate_relation_promotion(
        {
            "source_id": "prod_gpu",
            "target_id": "prod_cowos",
            "confidence": "high",
        },
        "announcement",
        "巨潮公告-扩产",
    )
    assert hard["can_confirm"] is True
    assert hard["hard_source_count"] >= 1


def test_normalize_extraction_new_product():
    from app.services import extraction as extraction_service

    normalized = extraction_service.normalize_extraction(
        {
            "relations": [
                {
                    "type": "UPSTREAM_OF",
                    "source_name": "硅光子芯片",
                    "target_name": "光模块",
                    "confidence": "medium",
                }
            ],
            "bottleneck_hints": [{"product_name": "硅光子芯片", "confidence": "low"}],
        },
        "sector_ai_compute",
        source_type="research_report",
        source_ref="测试-新环节",
    )
    assert len(normalized["new_products"]) == 1
    assert normalized["new_products"][0]["name"] == "硅光子芯片"
    assert normalized["relations"][0]["source_id"] == normalized["new_products"][0]["product_id"]
    assert normalized["relations"][0]["target_id"] == "prod_optical_module"
    assert normalized["bottleneck_hints"][0]["product_id"] == normalized["new_products"][0]["product_id"]


def test_confirm_draft_creates_new_product():
    from app.services import extraction as extraction_service

    store = get_store()
    draft = extraction_service.ingest_document(
        "sector_ai_compute",
        "research_report",
        "新环节测试研报",
        "硅光子芯片是光模块的上游，产能紧张属于瓶颈环节。",
    )
    new_name = "硅光子芯片"
    new_products = draft["extracted"].get("new_products", [])
    assert any(np["name"] == new_name for np in new_products)

    with pytest.raises(ValueError, match="多源交叉验证未通过"):
        extraction_service.confirm_draft(draft["draft_id"], force=False)

    result = extraction_service.confirm_draft(draft["draft_id"], force=True)
    assert result["status"] == "confirmed"
    assert len(result["applied_products"]) >= 1

    store = get_store()
    new_pid = next(np["product_id"] for np in new_products if np["name"] == new_name)
    product = store.get_product(new_pid)
    assert product is not None
    assert product["name"] == new_name

    upstream = store.upstream_of("prod_optical_module")
    assert new_pid in upstream


def test_empty_graph_when_demo_seed_disabled(monkeypatch):
    monkeypatch.setattr("app.config.LOAD_DEMO_SEED", False)
    from app.services.graph_store import get_store, invalidate_store_cache, set_store_from_db

    set_store_from_db(False)
    invalidate_store_cache()
    store = get_store()
    assert store.list_sectors() == []
    assert store.list_products() == []


def test_load_seed_if_empty_respects_demo_flag(monkeypatch):
    from app.db.session import init_db
    from app.ontology import pg_store
    from app.ontology.seed_loader import load_seed_if_empty

    if not init_db():
        return
    monkeypatch.setattr("app.config.LOAD_DEMO_SEED", False)
    pg_store.set_db_enabled(True)
    assert load_seed_if_empty() is False


def test_sector_bootstrap_orchestrator_step():
    r = client.post(
        "/api/v1/agents/orchestrator/run",
        json={
            "sector_id": "sector_ai_compute",
            "steps": ["sector_bootstrap"],
            "stop_on_gate": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["results"][0]["step"] == "sector_bootstrap"
    assert body["results"][0]["status"] == "ok"


def test_adopt_recommendation_auto_bootstrap(monkeypatch):
    from app.services import sector_adopt

    monkeypatch.setattr(
        sector_adopt,
        "bootstrap_sector",
        lambda sector_id, **kwargs: {
            "sector_id": sector_id,
            "constituents": {"status": "skipped", "reason": "test"},
            "report_draft": {"status": "empty"},
        },
    )
    rec = client.post(
        "/api/v1/agents/sector-recommend/run",
        json={"focus": "测试赛道", "max_recommendations": 1},
    )
    assert rec.status_code == 200
    items = rec.json().get("recommendations") or []
    if not items:
        return
    rec_id = items[0]["rec_id"]
    adopt = client.post(f"/api/v1/agents/sector-recommendations/{rec_id}/adopt")
    assert adopt.status_code == 200
    body = adopt.json()
    assert body.get("bootstrap") is not None


def test_agent_matrix_f6():
    matrix = client.get("/api/v1/agents/matrix")
    assert matrix.status_code == 200
    items = matrix.json()["items"]
    assert len(items) >= 8
    by_key = {x["agent_key"]: x for x in items}
    assert by_key["knowledge_ingest"]["agent_class"] == "A"
    assert by_key["bottleneck_scout"]["agent_class"] == "B"
    assert by_key["sector_recommend"]["runtime"] == "pipeline"

    orch = client.post(
        "/api/v1/agents/orchestrator/run",
        json={
            "sector_id": "sector_ai_compute",
            "steps": ["sector_recommend", "bear_case"],
            "stop_on_gate": True,
        },
    )
    assert orch.status_code == 200
    body = orch.json()
    assert body.get("agent_class") == "B"
    steps = body["results"]
    assert steps[0]["step"] == "sector_recommend"
    assert steps[0].get("agent_class") == "B"
    assert any(s["step"] == "bear_case" for s in steps)
