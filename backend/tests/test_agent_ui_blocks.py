"""agent_ui_blocks 单元测试。"""

from app.services.agent_ui_blocks import build_pending_todos_block, build_ui_blocks


def test_sector_recommend_blocks():
    blocks = build_ui_blocks(
        "sector_recommend",
        {
            "agent_summary": "发现 2 条推荐",
            "recommendations": [{"rec_id": "r1", "sector_name": "AI算力"}],
        },
    )
    types = [b["type"] for b in blocks]
    assert types == ["metric_cards", "sector_recommendation_list"]


def test_bottleneck_blocks():
    blocks = build_ui_blocks(
        "bottleneck_scout",
        {"recommendations": [{"rec_id": "b1", "product_name": "磷化铟"}]},
    )
    assert any(b["type"] == "bottleneck_rec_list" for b in blocks)


def test_report_graphrag_blocks():
    blocks = build_ui_blocks(
        "report_graphrag",
        {
            "agent_summary": "已生成草稿",
            "report_id": "rep_1",
            "report": {"report_id": "rep_1", "logic_chain_steps": 3, "status": "draft"},
        },
    )
    assert any(b["type"] == "report_draft_summary" for b in blocks)


def test_bear_case_blocks():
    blocks = build_ui_blocks(
        "bear_case",
        {
            "agent_summary": "2 条看空",
            "bear_case_count": 2,
            "high_unrebutted": 1,
            "sector_id": "sector_ai_compute",
            "bear_cases": [{"bear_id": "bear_1", "stock_code": "600000", "risk": "估值过高"}],
        },
    )
    types = [b["type"] for b in blocks]
    assert "metric_cards" in types
    assert "bear_case_list" in types
    metric = next(b for b in blocks if b["type"] == "metric_cards")
    keys = {m["key"] for m in metric["data"]["metrics"]}
    assert "bear_case_count" in keys
    assert "high_unrebutted" in keys


def test_monitor_watch_alert_feed():
    blocks = build_ui_blocks(
        "monitor_watch",
        {
            "alert_count": 2,
            "alerts": [{"type": "stale", "level": "medium", "message": "知识过期"}],
            "global_alerts": [{"type": "ods", "level": "low", "message": "ODS 延迟"}],
        },
    )
    assert any(b["type"] == "alert_feed" for b in blocks)
    feed = next(b for b in blocks if b["type"] == "alert_feed")
    assert len(feed["data"]["items"]) == 2


def test_knowledge_draft_with_extracted():
    blocks = build_ui_blocks(
        "knowledge_ingest",
        {
            "draft_id": "draft_1",
            "sector_id": "sector_ai_compute",
            "extracted": {"relations": [{"subject": "A", "predicate": "上游", "object": "B"}]},
        },
    )
    draft = next(b for b in blocks if b["type"] == "knowledge_draft_preview")
    assert draft["data"]["extracted"]["relations"][0]["subject"] == "A"
    assert draft["actions"][0]["action_id"] == "goto_knowledge"


def test_pending_todos_block():
    block = build_pending_todos_block(
        [{"type": "draft", "count": 2, "message": "待校准", "action": "Go", "route": "/knowledge"}],
        [{"type": "gate", "level": "high", "message": "未确认"}],
        resume_steps=["knowledge_ingest"],
    )
    assert block is not None
    assert block["type"] == "alert_feed"
    assert len(block["data"]["items"]) == 2
    assert block["actions"][0]["action_id"] == "resume_orchestrator"


def test_bottleneck_before_sector_in_intent():
    from app.services.intent_router import parse_intent

    r = parse_intent("扫描瓶颈", sector_id="sector_ai_compute")
    assert r["agent_key"] == "bottleneck_scout"

    r2 = parse_intent("运行反证", sector_id="sector_ai_compute")
    assert r2["agent_key"] == "bear_case"
