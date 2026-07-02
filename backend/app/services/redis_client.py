"""Redis 客户端 — 可选；不可用时优雅降级。"""

from __future__ import annotations

import logging
from typing import Any

from app.config import AGENT_SESSION_REDIS_ENABLED, REDIS_URL

logger = logging.getLogger(__name__)

_client: Any = None
_available: bool | None = None


def is_redis_available() -> bool:
    global _available, _client
    if AGENT_SESSION_REDIS_ENABLED == "off":
        return False
    if _available is not None:
        return _available
    try:
        client = get_redis_client()
        client.ping()
        _available = True
        return True
    except Exception as e:
        logger.info("Redis 不可用，会话将仅走 DB/内存: %s", e)
        _available = False
        _client = None
        return False


def get_redis_client():
    global _client
    if AGENT_SESSION_REDIS_ENABLED == "off":
        raise RuntimeError("Redis disabled")
    if _client is None:
        import redis

        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def reset_redis_client_for_tests() -> None:
    global _client, _available
    _client = None
    _available = None
