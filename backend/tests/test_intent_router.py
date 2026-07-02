"""intent_router 单元测试 + /agents/intent API。"""

from fastapi.testclient import TestClient

from app.main import app
from app.services.intent_router import parse_intent

client = TestClient(app)


def test_parse_intent_empty():
    r = parse_intent("")
    assert r["intent"] == "clarify"
    assert "suggested_chips" in r


def test_parse_intent_resume_requires_sector():
    r = parse_intent("从断点继续")
    assert r["intent"] == "clarify"


def test_parse_intent_resume_with_sector():
    r = parse_intent("断点续跑", sector_id="sector_ai_compute", workflow_step=3)
    assert r["intent"] == "run_agent"
    assert r["agent_key"] == "orchestrator"
    assert r["params"]["resume"] is True


def test_parse_intent_sector_recommend():
    r = parse_intent("推荐赛道", focus="AI算力")
    assert r["intent"] == "run_agent"
    assert r["agent_key"] == "sector_recommend"
    assert r["params"].get("focus") == "AI算力"


def test_parse_intent_sector_cold_start():
    r = parse_intent("发现景气赛道")
    assert r["intent"] == "run_agent"
    assert r["agent_key"] == "sector_recommend"
    assert r["params"].get("force_cold_start") is True


def test_parse_intent_bottleneck():
    r = parse_intent("扫描瓶颈", sector_id="sector_ai_compute")
    assert r["intent"] == "run_agent"
    assert r["agent_key"] == "bottleneck_scout"


def test_parse_intent_navigate_knowledge():
    r = parse_intent("上传研报", sector_id="sector_ai_compute")
    assert r["intent"] == "navigate"
    assert r["params"]["route"] == "/knowledge"


def test_intent_api():
    r = client.post(
        "/api/v1/agents/intent",
        json={"message": "候选融合", "sector_id": "sector_ai_compute"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "run_agent"
    assert body["agent_key"] == "candidate_fusion"
