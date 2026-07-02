"""workflow_progress 单元测试。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_workflow_status_unconfirmed_sector():
    r = client.get("/api/v1/sectors/sector_ai_compute/workflow-status")
    assert r.status_code == 200
    body = r.json()
    assert body["sector_id"] == "sector_ai_compute"
    assert "steps" in body
    assert len(body["steps"]) == 7
    step1 = body["steps"][0]
    if not body["sector_confirmed"]:
        assert step1["status"] in ("active", "done")
        blocked = [s for s in body["steps"][1:] if s["status"] == "blocked"]
        assert len(blocked) >= 1


def test_workflow_status_resume_steps():
    r = client.get("/api/v1/sectors/sector_ai_compute/workflow-status")
    assert r.status_code == 200
    body = r.json()
    assert "resume_steps" in body
    assert isinstance(body["resume_steps"], list)
    assert "sector_recommend" not in body["resume_steps"]


def test_orchestrator_resume_flag():
    r = client.post(
        "/api/v1/agents/orchestrator/run",
        json={
            "sector_id": "sector_ai_compute",
            "resume": True,
            "stop_on_gate": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    steps_run = [x["step"] for x in body["results"]]
    assert "sector_recommend" not in steps_run


def test_workflow_status_not_found():
    r = client.get("/api/v1/sectors/sector_does_not_exist/workflow-status")
    assert r.status_code == 404
