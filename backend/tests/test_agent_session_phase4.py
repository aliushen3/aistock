"""Phase 4 — 会话持久化 / LLM 意图 / SSE 流。"""

import json

from fastapi.testclient import TestClient

from app.main import app
from app.services.agent_session_store import create_session, get_session, update_session
from app.services.agent_stream import iter_session_message_stream, sse_encode
from app.services.intent_router import resolve_intent

client = TestClient(app)


def test_create_and_get_session():
    row = create_session(sector_id="sector_ai_compute", focus="AI算力", workflow_step=1)
    assert row["session_id"].startswith("sess_")
    loaded = get_session(row["session_id"])
    assert loaded is not None
    assert loaded["sector_id"] == "sector_ai_compute"
    assert loaded["focus"] == "AI算力"


def test_update_session_messages():
    row = create_session()
    updated = update_session(
        row["session_id"],
        {"messages": [{"id": "m1", "role": "user", "content": "扫描瓶颈", "timestamp": 1}]},
    )
    assert updated is not None
    assert len(updated["messages"]) == 1


def test_resolve_intent_rule_first():
    r = resolve_intent("扫描瓶颈", sector_id="sector_ai_compute", use_llm=False)
    assert r["router"] == "rule"
    assert r["agent_key"] == "bottleneck_scout"


def test_resolve_intent_unknown_without_llm():
    r = resolve_intent("随便说点什么听不懂", sector_id="sector_ai_compute", use_llm=False)
    assert r["intent"] == "unknown"


def test_session_api_crud():
    r = client.post("/api/v1/agents/sessions", json={"sector_id": "sector_ai_compute"})
    assert r.status_code == 200
    sid = r.json()["session_id"]
    g = client.get(f"/api/v1/agents/sessions/{sid}")
    assert g.status_code == 200
    p = client.put(
        f"/api/v1/agents/sessions/{sid}",
        json={"chips": ["发现景气赛道", "扫描瓶颈"]},
    )
    assert p.status_code == 200
    assert p.json()["chips"] == ["发现景气赛道", "扫描瓶颈"]
    d = client.delete(f"/api/v1/agents/sessions/{sid}")
    assert d.status_code == 200


def test_sse_stream_clarify():
    chunks = list(
        iter_session_message_stream(
            message="",
            intent={"intent": "clarify", "assistant_message": "请输入", "suggested_chips": []},
            stream_assistant=True,
        )
    )
    assert any("event: intent" in c for c in chunks)
    assert any("event: message_delta" in c for c in chunks)


def test_sse_encode_json():
    raw = sse_encode("test", {"a": 1})
    assert raw.startswith("event: test\n")
    assert json.loads(raw.split("data: ", 1)[1].strip()) == {"a": 1}


def test_intent_api_with_use_llm_flag():
    r = client.post(
        "/api/v1/agents/intent",
        json={"message": "扫描瓶颈", "sector_id": "sector_ai_compute", "use_llm": False},
    )
    assert r.status_code == 200
    assert r.json()["router"] == "rule"
