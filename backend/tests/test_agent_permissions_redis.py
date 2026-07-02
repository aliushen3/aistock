"""Block 权限与 Redis 会话缓存测试。"""

from unittest.mock import MagicMock, patch

from app.services.agent_block_permissions import (
    block_type_visible,
    filter_ui_blocks,
    get_interaction_permissions,
)
from app.services.agent_session_store import create_session, get_session, update_session
from app.services.redis_client import reset_redis_client_for_tests


def test_analyst_cannot_see_candidate_table():
    blocks = [
        {
            "block_id": "c1",
            "type": "candidate_fusion_table",
            "title": "候选",
            "data": {"items": []},
            "actions": [],
        }
    ]
    filtered = filter_ui_blocks(blocks, "analyst")
    assert filtered == []


def test_fund_manager_sees_candidate_table():
    blocks = [
        {
            "block_id": "c1",
            "type": "candidate_fusion_table",
            "title": "候选",
            "data": {"items": []},
            "actions": [{"action_id": "goto_candidates", "label": "去候选池"}],
        }
    ]
    filtered = filter_ui_blocks(blocks, "fund_manager")
    assert len(filtered) == 1
    assert filtered[0]["actions"][0]["action_id"] == "goto_candidates"


def test_interaction_permissions():
    perms = get_interaction_permissions("analyst")
    assert perms["adopt_sector"] is False
    assert perms["dismiss_proposal"] is True
    fm = get_interaction_permissions("fund_manager")
    assert fm["adopt_sector"] is True


def test_block_type_visible():
    assert block_type_visible("analyst", "metric_cards") is True
    assert block_type_visible("analyst", "candidate_fusion_table") is False
    assert block_type_visible("fund_manager", "candidate_fusion_table") is True


def test_redis_session_cache_read_through():
    reset_redis_client_for_tests()
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    mock_redis.setex.return_value = True

    with patch("app.services.agent_session_store.is_redis_available", return_value=True), patch(
        "app.services.redis_client.get_redis_client", return_value=mock_redis
    ), patch("app.services.agent_session_store.pg_store.is_db_enabled", return_value=False):
        row = create_session(operator="analyst", focus="AI")
        assert mock_redis.setex.called
        mock_redis.get.return_value = None
        loaded = get_session(row["session_id"])
        assert loaded is not None
        assert loaded["focus"] == "AI"

        updated = update_session(row["session_id"], {"chips": ["扫描瓶颈"]})
        assert updated["chips"] == ["扫描瓶颈"]
        assert mock_redis.setex.call_count >= 2


def test_ui_permissions_api():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get("/api/v1/agents/ui-permissions", headers={"X-Operator": "analyst"})
    assert r.status_code == 200
    body = r.json()
    assert body["operator"] == "analyst"
    assert body["blocks"]["candidate_fusion_table"] is False
    assert body["interactions"]["adopt_sector"] is False

    r2 = client.get("/api/v1/agents/ui-permissions", headers={"X-Operator": "fund_manager"})
    assert r2.json()["blocks"]["candidate_fusion_table"] is True
