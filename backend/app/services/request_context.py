"""HTTP 请求上下文 — operator 解析与 ContextVar。"""

from __future__ import annotations

import contextvars

from fastapi import Header

_operator_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("operator", default="analyst")


def resolve_operator(
    x_operator: str | None = None,
    body_operator: str | None = None,
) -> str:
    return (body_operator or x_operator or "analyst").strip() or "analyst"


def set_current_operator(operator: str) -> None:
    _operator_ctx.set(operator)


def get_current_operator() -> str:
    return _operator_ctx.get()


def bind_operator_header(x_operator: str | None = Header(default=None, alias="X-Operator")) -> None:
    """Router 级依赖：从 Header 绑定 operator。"""
    set_current_operator(resolve_operator(x_operator))
