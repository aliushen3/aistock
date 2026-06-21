"""异步知识抽取任务。"""

from __future__ import annotations

from app.celery_app import celery_app
from app.services import extraction as extraction_service
from app.services.minio_client import build_object_key, upload_text


@celery_app.task(bind=True, name="knowledge.ingest_document")
def ingest_document_task(
    self,
    sector_id: str,
    source_type: str,
    source_ref: str,
    content: str,
    operator: str = "analyst",
):
    self.update_state(state="PROGRESS", meta={"step": "uploading"})
    obj_key = build_object_key(sector_id, source_ref)
    storage_path = upload_text(obj_key, content)

    self.update_state(state="PROGRESS", meta={"step": "extracting"})
    draft = extraction_service.ingest_document(
        sector_id, source_type, source_ref, content, operator
    )
    if storage_path:
        draft["storage_path"] = storage_path
    return {
        "draft_id": draft["draft_id"],
        "status": draft["status"],
        "extracted": draft["extracted"],
        "storage_path": storage_path,
    }
