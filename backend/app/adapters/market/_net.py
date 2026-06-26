"""行情抓取网络助手 — 强制 IPv4 + 重试退避。

免费行情源（东财/新浪等）常出现 IPv6 解析可达但握手被重置（RemoteDisconnected），
以及偶发限流。这里集中处理：优先 IPv4、失败重试。
"""

from __future__ import annotations

import logging
import socket
import time
from typing import Callable, TypeVar

from app.config import MARKET_FORCE_IPV4, MARKET_HTTP_MAX_RETRY, MARKET_HTTP_RETRY_BACKOFF_SEC

logger = logging.getLogger(__name__)

T = TypeVar("T")

_ipv4_patched = False
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    results = _orig_getaddrinfo(host, port, family, type, proto, flags)
    ipv4 = [r for r in results if r[0] == socket.AF_INET]
    return ipv4 or results


def ensure_ipv4() -> None:
    """全局优先 IPv4 解析（幂等）。"""
    global _ipv4_patched
    if _ipv4_patched or not MARKET_FORCE_IPV4:
        return
    socket.getaddrinfo = _ipv4_only_getaddrinfo
    _ipv4_patched = True
    logger.info("行情抓取已启用强制 IPv4 解析")


def with_retry(fn: Callable[[], T], label: str = "market") -> T:
    """带退避重试地执行抓取函数，重试耗尽后抛出最后一次异常。"""
    last_exc: Exception | None = None
    for attempt in range(1, MARKET_HTTP_MAX_RETRY + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < MARKET_HTTP_MAX_RETRY:
                wait = MARKET_HTTP_RETRY_BACKOFF_SEC * attempt
                logger.warning("%s 抓取第 %d 次失败，%.1fs 后重试: %s", label, attempt, wait, exc)
                time.sleep(wait)
    assert last_exc is not None
    raise last_exc
