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
    clear_all()
    clear_pool_state()
    yield
    clear_all()
    clear_pool_state()


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

    result = action_executor.execute_with_params(
        action_type="ApprovePoolEntry",
        target_type="CandidatePoolEntry",
        target_id=entry_id,
        params={"reason": "双逻辑共振，逻辑成立"},
        operator="analyst",
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
    r = client.post(
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
    result = action_executor.execute_with_params(
        action_type="ConfirmBottleneck",
        target_type="Product",
        target_id=product_id,
        params={"reason": "扩产周期长，供需缺口明确"},
        operator="analyst",
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
    result = action_executor.execute_with_params(
        action_type="PublishReport",
        target_type="ResearchReport",
        target_id=report["report_id"],
        params={"comments": "逻辑链完整"},
        operator="analyst",
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
