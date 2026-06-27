"""测试辅助 — 重置 Ontology demo 种子。"""

from __future__ import annotations

from sqlalchemy import delete

from app.db.models import (
    OntBearCase,
    OntBottleneckRecommendation,
    OntCandidateEntry,
    OntCompany,
    OntEvidence,
    OntHintOutcome,
    OntKnowledgeDraft,
    OntLinkProduces,
    OntLinkUpstream,
    OntPendingReview,
    OntProduct,
    OntResearchReport,
    OntSector,
    OntSectorRecommendation,
    OntSerenityRecommendation,
    OntUploadedDocument,
)
from app.db.session import SessionLocal
from app.ontology import pg_store
from app.ontology.seed_loader import load_demo_seed_from_json
from app.services.graph_store import invalidate_store_cache, set_store_from_db

_RESET_MODELS = (
    OntLinkProduces,
    OntLinkUpstream,
    OntBearCase,
    OntCandidateEntry,
    OntPendingReview,
    OntKnowledgeDraft,
    OntHintOutcome,
    OntResearchReport,
    OntUploadedDocument,
    OntBottleneckRecommendation,
    OntSerenityRecommendation,
    OntSectorRecommendation,
    OntCompany,
    OntProduct,
    OntSector,
    OntEvidence,
)


def reload_demo_seed() -> None:
    db = SessionLocal()
    try:
        for model in _RESET_MODELS:
            db.execute(delete(model))
        db.commit()
    finally:
        db.close()
    pg_store.set_db_enabled(True)
    load_demo_seed_from_json()
    set_store_from_db(True)
    invalidate_store_cache()
