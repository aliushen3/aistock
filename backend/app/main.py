from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, sectors, graph, candidates, reasoning

app = FastAPI(
    title="AiStock API",
    description="知识驱动的定性投研辅助系统",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(sectors.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")
app.include_router(candidates.router, prefix="/api/v1")
app.include_router(reasoning.router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "name": "AiStock",
        "positioning": "知识驱动的定性投研辅助系统",
        "note": "量化打分仅作辅助提示，不构成自动投资决策",
    }
