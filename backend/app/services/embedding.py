"""文本向量化 — OpenAI 兼容 embedding API，无 Key 时降级伪向量。"""

from __future__ import annotations

import logging
import re

from app.config import EMBEDDING_DIM, EMBEDDING_ENABLED, EMBEDDING_MODEL, LLM_API_KEY, LLM_BASE_URL

logger = logging.getLogger(__name__)

PSEUDO_DIM = 8


def is_real_embedding_enabled() -> bool:
    if EMBEDDING_ENABLED == "off":
        return False
    if EMBEDDING_ENABLED == "on":
        return bool(LLM_API_KEY)
    return bool(LLM_API_KEY)


def embedding_dim() -> int:
    return EMBEDDING_DIM if is_real_embedding_enabled() else PSEUDO_DIM


def _pseudo_vector(text: str, dim: int = PSEUDO_DIM) -> list[float]:
    vec = [0.0] * dim
    for ch in text:
        vec[ord(ch) % dim] += 1.0
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]


def embed_text(text: str) -> list[float]:
    """单条文本 embedding；失败时降级伪向量。"""
    if not text.strip():
        return _pseudo_vector("empty", embedding_dim())
    if not is_real_embedding_enabled():
        return _pseudo_vector(text, PSEUDO_DIM)
    try:
        from openai import OpenAI

        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text[:8000])
        vec = resp.data[0].embedding
        if len(vec) != EMBEDDING_DIM:
            logger.warning("embedding 维度 %s 与配置 %s 不一致", len(vec), EMBEDDING_DIM)
        return vec
    except Exception as e:
        logger.warning("embedding API 失败，降级伪向量: %s", e)
        return _pseudo_vector(text, PSEUDO_DIM)


def embed_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if not is_real_embedding_enabled():
        return [_pseudo_vector(t, PSEUDO_DIM) for t in texts]
    try:
        from openai import OpenAI

        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        inputs = [t[:8000] for t in texts]
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=inputs)
        ordered = sorted(resp.data, key=lambda x: x.index)
        return [item.embedding for item in ordered]
    except Exception as e:
        logger.warning("batch embedding 失败，降级伪向量: %s", e)
        return [_pseudo_vector(t, PSEUDO_DIM) for t in texts]


def embedding_mode() -> str:
    return "openai_compatible" if is_real_embedding_enabled() else "pseudo_hash"
