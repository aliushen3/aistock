"""Qdrant 向量检索 + 关键词 fallback（GraphRAG 混合检索）。"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.config import QDRANT_COLLECTION, QDRANT_DOCUMENTS_COLLECTION, QDRANT_URL
from app.services.embedding import embed_batch, embed_text, embedding_dim, embedding_mode, is_real_embedding_enabled

logger = logging.getLogger(__name__)

_available: bool | None = None
_indexed_ids: set[str] = set()
_indexed_chunks: list[dict] = []


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]{2,}", text.lower()))


def _keyword_score(query: str, text: str) -> float:
    q_tokens = _tokenize(query)
    if not q_tokens:
        return 0.0
    text_l = text.lower()
    hits = sum(1 for t in q_tokens if t in text_l)
    return hits / len(q_tokens)


def is_qdrant_available() -> bool:
    global _available
    if _available is not None:
        return _available
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=QDRANT_URL, timeout=3)
        client.get_collections()
        _available = True
    except Exception as e:
        logger.warning("Qdrant 不可用，使用关键词检索 fallback: %s", e)
        _available = False
    return _available


def _ensure_collection(client, collection_name: str = QDRANT_COLLECTION) -> None:
    from qdrant_client.models import Distance, VectorParams

    size = embedding_dim()
    names = [c.name for c in client.get_collections().collections]
    if collection_name in names:
        info = client.get_collection(collection_name)
        current_size = info.config.params.vectors.size
        if current_size != size:
            client.delete_collection(collection_name)
            names.remove(collection_name)
    if collection_name not in names:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=size, distance=Distance.COSINE),
        )


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    """按固定窗口分块，保留重叠以提升检索召回。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _point_id(key: str) -> int:
    return abs(hash(key)) % (2**63 - 1)


def get_vector_backend_info() -> dict:
    return {
        "mode": embedding_mode(),
        "real_enabled": is_real_embedding_enabled(),
        "dimension": embedding_dim(),
    }


def index_evidence(evidence_list: list[dict]) -> dict:
    """将证据索引到 Qdrant；失败时仅记录内存 ID。"""
    global _indexed_ids
    indexed = 0
    if not is_qdrant_available():
        _indexed_ids = {e["id"] for e in evidence_list}
        return {"status": "fallback", "count": len(_indexed_ids)}

    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct

    client = QdrantClient(url=QDRANT_URL, timeout=10)
    _ensure_collection(client)
    points = []
    texts = [f"{e.get('source_ref', '')} {e.get('excerpt', '')}" for e in evidence_list]
    vectors = embed_batch(texts)
    for e, vector, text in zip(evidence_list, vectors, texts):
        points.append(
            PointStruct(
                id=abs(hash(e["id"])) % (2**63 - 1),
                vector=vector,
                payload={
                    "ref_id": e["id"],
                    "source_type": e.get("source_type"),
                    "source_ref": e.get("source_ref"),
                    "excerpt": e.get("excerpt"),
                    "text": text,
                },
            )
        )
    if points:
        client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    _indexed_ids = {e["id"] for e in evidence_list}
    indexed = len(points)
    return {"status": "ok", "count": indexed}


def search_evidence(query: str, evidence_list: list[dict], top_k: int = 5) -> list[dict]:
    """混合检索：Qdrant 优先，关键词 overlap fallback。"""
    if is_qdrant_available():
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(url=QDRANT_URL, timeout=5)
            hits = client.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=embed_text(query),
                limit=top_k,
            )
            if hits:
                return [
                    {
                        "ref_id": h.payload.get("ref_id"),
                        "source_type": h.payload.get("source_type"),
                        "source_ref": h.payload.get("source_ref"),
                        "excerpt": h.payload.get("excerpt"),
                        "score": float(h.score),
                        "retrieval": "qdrant",
                    }
                    for h in hits
                ]
        except Exception as e:
            logger.warning("Qdrant 检索失败: %s", e)

    scored: list[tuple[float, dict]] = []
    for e in evidence_list:
        text = f"{e.get('source_ref', '')} {e.get('excerpt', '')}"
        overlap = _keyword_score(query, text)
        if overlap > 0:
            scored.append((overlap, e))
    scored.sort(key=lambda x: -x[0])
    return [
        {
            "ref_id": e["id"],
            "source_type": e.get("source_type"),
            "source_ref": e.get("source_ref"),
            "excerpt": e.get("excerpt"),
            "score": round(score, 3),
            "retrieval": "keyword",
        }
        for score, e in scored[:top_k]
    ]


def index_document_chunks(
    doc_id: str,
    sector_id: str,
    source_ref: str,
    chunks: list[str],
    source_type: str = "research_report",
) -> dict:
    """将研报分块写入 Qdrant 文档集合；失败时保留内存索引。"""
    global _indexed_chunks
    entries = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}#{i}"
        entries.append(
            {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "sector_id": sector_id,
                "source_type": source_type,
                "source_ref": source_ref,
                "chunk_index": i,
                "excerpt": chunk[:300],
                "text": chunk,
            }
        )
    _indexed_chunks = [c for c in _indexed_chunks if c.get("doc_id") != doc_id] + entries

    if not is_qdrant_available():
        return {"status": "fallback", "count": len(entries)}

    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct

    client = QdrantClient(url=QDRANT_URL, timeout=10)
    _ensure_collection(client, QDRANT_DOCUMENTS_COLLECTION)
    points = []
    texts = [e["text"] for e in entries]
    vectors = embed_batch(texts)
    for e, vector in zip(entries, vectors):
        points.append(
            PointStruct(
                id=_point_id(e["chunk_id"]),
                vector=vector,
                payload={
                    "chunk_id": e["chunk_id"],
                    "doc_id": e["doc_id"],
                    "sector_id": e["sector_id"],
                    "source_type": e["source_type"],
                    "source_ref": e["source_ref"],
                    "chunk_index": e["chunk_index"],
                    "excerpt": e["excerpt"],
                    "text": e["text"],
                    "doc_type": "uploaded_report",
                },
            )
        )
    if points:
        client.upsert(collection_name=QDRANT_DOCUMENTS_COLLECTION, points=points)
    return {"status": "ok", "count": len(points)}


def search_documents(
    query: str,
    sector_id: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    """检索上传研报分块；Qdrant 优先，关键词 fallback。"""
    if is_qdrant_available():
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            client = QdrantClient(url=QDRANT_URL, timeout=5)
            flt = None
            if sector_id:
                flt = Filter(must=[FieldCondition(key="sector_id", match=MatchValue(value=sector_id))])
            hits = client.search(
                collection_name=QDRANT_DOCUMENTS_COLLECTION,
                query_vector=embed_text(query),
                query_filter=flt,
                limit=top_k,
            )
            if hits:
                return [
                    {
                        "ref_id": h.payload.get("chunk_id"),
                        "doc_id": h.payload.get("doc_id"),
                        "source_type": h.payload.get("source_type"),
                        "source_ref": h.payload.get("source_ref"),
                        "excerpt": h.payload.get("excerpt"),
                        "score": float(h.score),
                        "retrieval": "qdrant",
                        "doc_type": "uploaded_report",
                    }
                    for h in hits
                ]
        except Exception as e:
            logger.warning("Qdrant 文档检索失败: %s", e)

    pool = _indexed_chunks
    if sector_id:
        pool = [c for c in pool if c.get("sector_id") == sector_id]
    scored: list[tuple[float, dict]] = []
    for c in pool:
        text = f"{c.get('source_ref', '')} {c.get('text', '')}"
        overlap = _keyword_score(query, text)
        if overlap > 0:
            scored.append((overlap, c))
    scored.sort(key=lambda x: -x[0])
    return [
        {
            "ref_id": c["chunk_id"],
            "doc_id": c["doc_id"],
            "source_type": c.get("source_type"),
            "source_ref": c.get("source_ref"),
            "excerpt": c.get("excerpt"),
            "score": round(score, 3),
            "retrieval": "keyword",
            "doc_type": "uploaded_report",
        }
        for score, c in scored[:top_k]
    ]


def search_hybrid(
    query: str,
    evidence_list: list[dict],
    sector_id: str | None = None,
    top_k: int = 6,
) -> list[dict]:
    """证据 + 上传研报混合检索，按分数去重合并。"""
    ev_hits = search_evidence(query, evidence_list, top_k=top_k)
    doc_hits = search_documents(query, sector_id=sector_id, top_k=top_k)
    merged: dict[str, dict] = {}
    for hit in ev_hits + doc_hits:
        rid = hit.get("ref_id") or hit.get("doc_id")
        if not rid:
            continue
        prev = merged.get(rid)
        if prev is None or hit.get("score", 0) > prev.get("score", 0):
            merged[rid] = hit
    ranked = sorted(merged.values(), key=lambda x: -x.get("score", 0))
    return ranked[:top_k]
