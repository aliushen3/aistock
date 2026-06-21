"""MinIO 文档存储 — 公告/研报原文归档。"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone

from app.config import (
    MINIO_ACCESS_KEY,
    MINIO_BUCKET,
    MINIO_ENDPOINT,
    MINIO_SECRET_KEY,
)

logger = logging.getLogger(__name__)

_available: bool | None = None


def is_minio_available() -> bool:
    global _available
    if _available is not None:
        return _available
    try:
        from minio import Minio

        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False,
        )
        if not client.bucket_exists(MINIO_BUCKET):
            client.make_bucket(MINIO_BUCKET)
        _available = True
    except Exception as e:
        logger.warning("MinIO 不可用: %s", e)
        _available = False
    return _available


def upload_text(object_key: str, content: str, content_type: str = "text/plain") -> str | None:
    if not is_minio_available():
        return None
    from minio import Minio

    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )
    data = content.encode("utf-8")
    client.put_object(
        MINIO_BUCKET,
        object_key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return f"{MINIO_BUCKET}/{object_key}"


def upload_file(object_key: str, data: bytes, content_type: str = "application/octet-stream") -> str | None:
    if not is_minio_available():
        return None
    from minio import Minio

    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )
    client.put_object(
        MINIO_BUCKET,
        object_key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return f"{MINIO_BUCKET}/{object_key}"


def build_file_object_key(sector_id: str, filename: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in filename)[:64]
    return f"{sector_id}/{ts}/{safe}"


def build_object_key(sector_id: str, source_ref: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in source_ref)[:48]
    return f"{sector_id}/{ts}/{safe}.txt"
