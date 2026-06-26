"""A 股代码规范化与估值分位计算。"""

from __future__ import annotations

import re


def is_real_a_share_code(code: str) -> bool:
    digits = re.sub(r"\D", "", code or "")
    return len(digits) == 6 and digits.isdigit()


def normalize_display_code(code: str) -> str:
    digits = re.sub(r"\D", "", code or "")
    return digits.zfill(6)[-6:] if digits else code


def to_ts_code(code: str) -> str:
    digits = normalize_display_code(code)
    if not is_real_a_share_code(digits):
        return code
    suffix = "SH" if digits.startswith(("5", "6", "9")) else "SZ"
    return f"{digits}.{suffix}"


def to_akshare_symbol(code: str) -> str:
    digits = normalize_display_code(code)
    if not is_real_a_share_code(digits):
        return digits
    prefix = "sh" if digits.startswith(("5", "6", "9")) else "sz"
    return f"{prefix}{digits}"


def pe_percentile_from_series(values: list[float]) -> float | None:
    cleaned = [v for v in values if v is not None and v > 0]
    if len(cleaned) < 20:
        return None
    current = cleaned[-1]
    rank = sum(1 for v in cleaned if v <= current) / len(cleaned)
    return round(rank, 4)
