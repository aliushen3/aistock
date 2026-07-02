"""sector_board_config 单元测试。"""

from fastapi.testclient import TestClient

from app.main import app
from app.services.sector_board_config import (
    get_sector_board_config,
    get_sector_board_config_meta,
    save_sector_board_config,
)

client = TestClient(app)


def test_get_config_json_seed_fallback():
    cfg = get_sector_board_config("sector_ai_compute")
    assert cfg is not None
    assert len(cfg.get("boards", [])) >= 1


def test_constituent_config_api_get():
    r = client.get("/api/v1/sectors/sector_ai_compute/constituent-config")
    assert r.status_code == 200
    body = r.json()
    assert body["sector_id"] == "sector_ai_compute"
    assert "config" in body
    assert body["source"] in ("db", "json_seed", "none")


def test_constituent_config_save_and_read():
    from app.ontology import pg_store

    if not pg_store.is_db_enabled():
        return
    meta = save_sector_board_config(
        "sector_ai_compute",
        {
            "boards": [{"type": "concept", "name": "测试板块"}],
            "default_product_id": "prod_optical_module",
            "product_keywords": {"prod_optical_module": ["测试"]},
        },
    )
    assert meta["source"] == "db"
    assert meta["config"]["boards"][0]["name"] == "测试板块"
    cfg = get_sector_board_config("sector_ai_compute")
    assert cfg["boards"][0]["name"] == "测试板块"


def test_import_seed_endpoint():
    r = client.post("/api/v1/sectors/sector_ai_compute/constituent-config/import-seed")
    if r.status_code == 400:
        return
    assert r.status_code == 200
    assert r.json()["source"] == "db"
