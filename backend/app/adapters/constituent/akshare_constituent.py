"""AkShare 板块成分股适配器 — 概念/行业板块真实上市公司。"""

from __future__ import annotations

import logging
import time

from app.adapters.market._net import ensure_ipv4, with_retry
from app.adapters.market._utils import is_real_a_share_code, normalize_display_code
from app.config import AKSHARE_RATE_LIMIT_SEC

logger = logging.getLogger(__name__)


class AkshareConstituentError(Exception):
    """AkShare 成分股拉取失败。"""


def _load_akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise AkshareConstituentError("未安装 akshare，请 pip install akshare") from exc
    return ak


def _sleep_rate_limit() -> None:
    if AKSHARE_RATE_LIMIT_SEC > 0:
        time.sleep(AKSHARE_RATE_LIMIT_SEC)


def _parse_market_cap(raw) -> float | None:
    if raw is None:
        return None
    try:
        text = str(raw).replace(",", "").strip()
        if not text or text in ("-", "--"):
            return None
        val = float(text)
        if val <= 0:
            return None
        if val > 1_000_000:
            return round(val / 100_000_000, 2)
        return round(val, 2)
    except (TypeError, ValueError):
        return None


def _row_to_record(row, board_type: str, board_name: str) -> dict | None:
    code_raw = row.get("代码") or row.get("code") or row.get("stock_code")
    name = row.get("名称") or row.get("name")
    if not code_raw or not name:
        return None
    code = normalize_display_code(str(code_raw))
    if not is_real_a_share_code(code):
        return None
    cap = None
    for key in ("总市值", "市值", "market_cap"):
        if key in row:
            cap = _parse_market_cap(row[key])
            if cap is not None:
                break
    return {
        "stock_code": code,
        "name": str(name).strip(),
        "market_cap_billion": cap,
        "board_type": board_type,
        "board_name": board_name,
    }


def fetch_board_rows(board_type: str, board_name: str) -> list[dict]:
    """拉取板块成分并标准化为 ConstituentRecord 列表。"""
    ak = _load_akshare()
    ensure_ipv4()
    _sleep_rate_limit()
    btype = (board_type or "concept").lower()
    if btype == "industry":
        df = with_retry(
            lambda: ak.stock_board_industry_cons_em(symbol=board_name),
            label=f"akshare industry cons {board_name}",
        )
    else:
        df = with_retry(
            lambda: ak.stock_board_concept_cons_em(symbol=board_name),
            label=f"akshare concept cons {board_name}",
        )
    if df is None or getattr(df, "empty", True):
        return []
    records: list[dict] = []
    for _, row in df.iterrows():
        rec = _row_to_record(row.to_dict(), btype, board_name)
        if rec:
            records.append(rec)
    return records


class AkshareConstituentAdapter:
    name = "akshare"

    def __init__(self) -> None:
        try:
            _load_akshare()
            self.mode = "live"
        except AkshareConstituentError:
            self.mode = "stub"

    def fetch_board_constituents(self, board_type: str, board_name: str) -> list[dict]:
        if self.mode != "live":
            return []
        try:
            return fetch_board_rows(board_type, board_name)
        except Exception as exc:
            logger.warning("AkShare 成分股拉取失败 %s/%s: %s", board_type, board_name, exc)
            return []
