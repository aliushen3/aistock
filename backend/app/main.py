from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, sectors, graph, candidates, reasoning, ontology, metrics, knowledge, diagnosis, alerts, agents, data


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import init_db
    from app.ontology import pg_store
    from app.ontology.seed_loader import load_seed_if_empty
    from app.services.graph_store import get_store, invalidate_store_cache, set_store_from_db
    from app.services.metrics import load_metrics_seed_if_empty
    from app.ontology.graph_projector import project_graph
    from app.services.vector_store import index_evidence

    from app.services.ods_service import seed_ods_metrics_if_empty

    if init_db():
        pg_store.set_db_enabled(True)
        seeded = load_seed_if_empty()
        load_metrics_seed_if_empty()
        seed_ods_metrics_if_empty()
        set_store_from_db(True)
        invalidate_store_cache()
        if seeded:
            project_graph()
    else:
        invalidate_store_cache()

    store = get_store()
    if store.evidence:
        index_evidence(list(store.evidence.values()))
    yield


app = FastAPI(
    title="AiStock API",
    description="知识驱动的定性投研辅助系统",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(sectors.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")
app.include_router(candidates.router, prefix="/api/v1")
app.include_router(reasoning.router, prefix="/api/v1")
app.include_router(ontology.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(diagnosis.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "name": "AiStock",
        "positioning": "知识驱动的定性投研辅助系统",
        "note": "量化打分仅作辅助提示，不构成自动投资决策",
    }
