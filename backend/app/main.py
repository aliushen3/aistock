from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, sectors, graph, candidates, reasoning, ontology


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import init_db
    from app.ontology import pg_store
    from app.ontology.seed_loader import load_seed_if_empty
    from app.services.graph_store import invalidate_store_cache, set_store_from_db

    if init_db():
        pg_store.set_db_enabled(True)
        load_seed_if_empty()
        set_store_from_db(True)
        invalidate_store_cache()
    yield


app = FastAPI(
    title="AiStock API",
    description="知识驱动的定性投研辅助系统",
    version="0.3.0",
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


@app.get("/")
def root():
    return {
        "name": "AiStock",
        "positioning": "知识驱动的定性投研辅助系统",
        "note": "量化打分仅作辅助提示，不构成自动投资决策",
    }
