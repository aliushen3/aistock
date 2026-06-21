"""研报/公告文件解析 — 提取纯文本供分块索引与知识抽取。"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
MAX_FILE_BYTES = 20 * 1024 * 1024


def _decode_text(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def _parse_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(parts)


def parse_document(filename: str, data: bytes) -> str:
    """按扩展名解析文件正文；不支持或过大时抛 ValueError。"""
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"文件过大，上限 {MAX_FILE_BYTES // (1024 * 1024)}MB")

    ext = ""
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        ext = f".{ext}"

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的文件类型: {ext or '未知'}，支持 {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

    if ext in (".txt", ".md"):
        text = _decode_text(data)
    elif ext == ".pdf":
        text = _parse_pdf(data)
    elif ext == ".docx":
        text = _parse_docx(data)
    else:
        raise ValueError(f"不支持的文件类型: {ext}")

    text = text.strip()
    if len(text) < 20:
        raise ValueError("未能从文件中提取有效文本（至少 20 字）")
    return text


def guess_content_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "txt": "text/plain",
        "md": "text/markdown",
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(ext, "application/octet-stream")
