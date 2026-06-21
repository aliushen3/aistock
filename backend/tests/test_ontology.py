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
    from app.ontology.property_overlays import set_product_property, set_sector_property
    from app.services.bearcase_store import clear_bear_state

    clear_all()
    clear_pool_state()
    clear_bear_state()
    set_sector_property("sector_ai_compute", "status", "beta_confirmed")
    set_sector_property("sector_ai_compute", "human_confirmed", True)
    set_product_property("prod_cowos", "bottleneck_status", "bottleneck_confirmed")
    set_product_property("prod_low_dk_glass", "serenity_niche_confirmed", True)
    yield
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


def test_wind_and_cninfo_adapters():
    from app.adapters.registry import get_adapter, list_adapters

    names = {a["name"] for a in list_adapters()}
    assert {"mock", "wind", "cninfo"}.issubset(names)

    wind = get_adapter("wind")
    assert wind.mode == "stub"
    sync = wind.fetch_industry_metrics("sector_ai_compute")
    assert len(sync) >= 1

    r = client.post(
        "/api/v1/data/sync/metrics/sector_ai_compute",
        params={"adapter": "wind"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "skipped")
    assert body.get("adapter") == "wind" or body.get("count", 0) >= 1

    ann = client.post(
        "/api/v1/data/sync/announcements/sector_ai_compute",
        params={"adapter": "cninfo"},
    )
    assert ann.status_code == 200
    assert ann.json()["adapter"] == "cninfo"
    assert ann.json()["count"] >= 1

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert "data_adapters" in health.json()["components"]


def test_wind_live_client(monkeypatch):
    from app.adapters.wind_client import WindClient
    from app.adapters.wind_provider import WindDataAdapter

    sample = [
        {
            "sector_id": "sector_ai_compute",
            "product_id": "prod_gpu",
            "metric_key": "capacity_utilization",
            "period": "2024Q4",
            "value": 0.92,
            "unit": "ratio",
        }
    ]

    def fake_request(self, method, path, params=None):
        if path == "/v1/industry-metrics":
            return {"items": sample}
        if path == "/v1/market-daily":
            return {"items": [{"stock_code": "600000", "trade_date": "2024-01-01", "market_cap_billion": 10}]}
        return {"items": []}

    monkeypatch.setenv("WIND_API_KEY", "test-key")
    monkeypatch.setattr(WindClient, "_request", fake_request)

    adapter = WindDataAdapter()
    assert adapter.mode == "live"
    rows = adapter.fetch_industry_metrics("sector_ai_compute")
    assert rows[0]["metric_key"] == "capacity_utilization"
    assert rows[0]["value"] == 0.92


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
