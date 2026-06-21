from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services import extraction as extraction_service
from app.services.document_parser import guess_content_type, parse_document
from app.services.document_store import create_document_record, list_documents
from app.services.graph_store import get_store
from app.services.minio_client import build_file_object_key, build_object_key, upload_file, upload_text
from app.services.vector_store import chunk_text, index_document_chunks

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/stale")
def list_stale_knowledge(sector_id: str | None = None):
    """保鲜过期（freshness=stale）知识清单（主线二）。"""
    from app.ontology.property_overlays import merge_product
    from app.services.freshness import product_freshness

    store = get_store()
    items = []
    for p in store.list_products(sector_id):
        merged = merge_product(p, p["id"]) or p
        fr = product_freshness(merged)
        if fr["freshness"] == "stale":
            items.append(
                {
                    "product_id": p["id"],
                    "product_name": p["name"],
                    "freshness": fr["freshness"],
                    "valid_until": fr["valid_until"],
                    "age_days": fr["age_days"],
                    "last_verified_at": merged.get("last_verified_at"),
                }
            )
    return {"count": len(items), "items": items, "note": "stale 知识不参与提示分或显著降权，需复核刷新"}


class IngestRequest(BaseModel):
    sector_id: str
    source_type: str = "research_report"
    source_ref: str
    content: str = Field(..., min_length=20)
    operator: str = "analyst"


@router.post("/upload")
async def upload_research_report(
    file: UploadFile = File(...),
    sector_id: str = Form(...),
    source_ref: str = Form(""),
    extract_knowledge: bool = Form(True),
    operator: str = Form("analyst"),
):
    """上传外部研报文件 → MinIO 归档 + Qdrant 分块索引（替代外部研报 API）。"""
    if get_store().get_sector(sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")

    filename = file.filename or "upload.txt"
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件为空")

    try:
        text = parse_document(filename, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    ref = source_ref.strip() or filename
    content_type = file.content_type or guess_content_type(filename)
    obj_key = build_file_object_key(sector_id, filename)
    storage_path = upload_file(obj_key, data, content_type)

    chunks = chunk_text(text)
    doc = create_document_record(
        sector_id=sector_id,
        source_ref=ref,
        filename=filename,
        content_type=content_type,
        storage_path=storage_path,
        char_count=len(text),
        chunk_count=len(chunks),
        operator=operator,
    )
    from app.services.ods_service import register_uploaded_report

    register_uploaded_report(doc)
    index_result = index_document_chunks(
        doc_id=doc["doc_id"],
        sector_id=sector_id,
        source_ref=ref,
        chunks=chunks,
        source_type="research_report",
    )

    draft = None
    if extract_knowledge:
        draft = extraction_service.ingest_document(
            sector_id, "research_report", ref, text, operator
        )

    return {
        "doc_id": doc["doc_id"],
        "source_ref": ref,
        "filename": filename,
        "char_count": len(text),
        "chunk_count": len(chunks),
        "storage_path": storage_path,
        "vector_index": index_result,
        "draft_id": draft["draft_id"] if draft else None,
        "message": "研报已上传并写入向量库",
    }


@router.get("/documents")
def get_uploaded_documents(sector_id: str | None = None):
    return {"items": list_documents(sector_id)}


@router.post("/ingest")
def ingest_document(req: IngestRequest):
    """知识抽取：文本 → 草案三元组（规则版，可扩展 LLM）。"""
    if get_store().get_sector(req.sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")
    draft = extraction_service.ingest_document(
        req.sector_id, req.source_type, req.source_ref, req.content, req.operator
    )
    return {
        "draft_id": draft["draft_id"],
        "status": draft["status"],
        "extracted": draft["extracted"],
        "message": "草案已生成，须经专家校准（CalibrateChain）后生效",
    }


@router.post("/ingest/async")
def ingest_document_async(req: IngestRequest):
    """异步知识抽取（Celery）；Worker 不可用时同步执行。"""
    if get_store().get_sector(req.sector_id) is None:
        raise HTTPException(status_code=404, detail="赛道不存在")

    try:
        from app.tasks.knowledge_tasks import ingest_document_task

        task = ingest_document_task.delay(
            req.sector_id,
            req.source_type,
            req.source_ref,
            req.content,
            req.operator,
        )
        return {"task_id": task.id, "status": "queued", "mode": "celery"}
    except Exception:
        obj_key = build_object_key(req.sector_id, req.source_ref)
        storage_path = upload_text(obj_key, req.content)
        draft = extraction_service.ingest_document(
            req.sector_id, req.source_type, req.source_ref, req.content, req.operator
        )
        return {
            "task_id": None,
            "status": "completed",
            "mode": "sync_fallback",
            "draft_id": draft["draft_id"],
            "storage_path": storage_path,
            "extracted": draft["extracted"],
        }


@router.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    try:
        from app.celery_app import celery_app

        result = celery_app.AsyncResult(task_id)
        payload = {"task_id": task_id, "state": result.state}
        if result.ready():
            if result.successful():
                payload["result"] = result.result
            else:
                payload["error"] = str(result.result)
        elif result.state == "PROGRESS":
            payload["meta"] = result.info
        return payload
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/drafts")
def list_drafts(sector_id: str | None = None):
    return {"items": extraction_service.list_drafts(sector_id)}


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str):
    draft = extraction_service.get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="草案不存在")
    return draft


@router.get("/drafts/{draft_id}/validate")
def validate_draft_endpoint(draft_id: str):
    """多源交叉 / 卖方去偏校验（F5）。"""
    try:
        return extraction_service.validate_draft(draft_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/drafts/{draft_id}/confirm")
def confirm_draft(draft_id: str, operator: str = "analyst", force: bool = False):
    try:
        return extraction_service.confirm_draft(draft_id, operator, force=force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
