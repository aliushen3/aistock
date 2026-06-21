from fastapi import APIRouter

from app.ontology import pg_store
from app.ontology.graph_projector import is_neo4j_available
from app.services.graph_store import get_store
from app.services.llm_client import is_llm_enabled
from app.services.minio_client import is_minio_available
from app.services.neo4j_traversal import sector_upstream_stats
from app.services.ods_service import ods_stats
from app.services.vector_store import get_vector_backend_info, is_qdrant_available
from app.adapters.registry import list_adapters

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    store = get_store()
    sector_id = "sector_ai_compute"
    neo_stats = sector_upstream_stats(sector_id) if is_neo4j_available() else None
    return {
        "status": "ok",
        "service": "aistock-api",
        "components": {
            "postgresql": pg_store.is_db_enabled(),
            "neo4j": is_neo4j_available(),
            "neo4j_traversal": getattr(store, "traversal_backend", "memory"),
            "neo4j_stats": neo_stats,
            "qdrant": is_qdrant_available(),
            "embedding": get_vector_backend_info(),
            "minio": is_minio_available(),
            "llm": is_llm_enabled(),
            "ods": ods_stats(),
            "data_adapter": __import__("app.config", fromlist=["DATA_ADAPTER"]).DATA_ADAPTER,
            "data_adapters": list_adapters(),
        },
    }
