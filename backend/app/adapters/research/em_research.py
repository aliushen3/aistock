"""东方财富研报适配器 — AkShare stock_research_report_em（免费）。

输出对齐 ods_external_report。走 eastmoney，注意代理/IPv4。
"""

from __future__ import annotations

import hashlib
import logging

from app.adapters.market._net import ensure_ipv4, with_retry
from app.adapters.market._utils import is_real_a_share_code, normalize_display_code

logger = logging.getLogger(__name__)


def _load_akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("未安装 akshare，请 pip install akshare") from exc
    return ak


def _pick(row, *names):
    for n in names:
        if n in row and str(row.get(n)) not in ("", "nan", "None"):
            return row.get(n)
    return None


def _report_key(code: str, title: str, date: str) -> str:
    digest = hashlib.md5(f"{code}|{title}|{date}".encode("utf-8")).hexdigest()[:16]
    return f"em_{code}_{digest}"


def _fetch_one(code: str, limit: int) -> list[dict]:
    ak = _load_akshare()
    ensure_ipv4()
    df = with_retry(
        lambda: ak.stock_research_report_em(symbol=code),
        label=f"em research {code}",
    )
    if df is None or getattr(df, "empty", True):
        return []
    rows: list[dict] = []
    for _, r in df.iterrows():
        title = _pick(r, "报告名称", "title")
        if not title:
            continue
        report_date = str(_pick(r, "报告日期", "日期") or "")[:10]
        org = _pick(r, "机构", "机构简称")
        rating = _pick(r, "东财评级", "评级", "投资评级")
        rows.append(
            {
                "report_key": _report_key(code, str(title), report_date),
                "stock_code": code,
                "title": str(title)[:512],
                "org_name": str(org)[:128] if org else None,
                "rating": str(rating)[:64] if rating else None,
                "report_date": report_date or None,
                "url": None,
            }
        )
        if len(rows) >= limit:
            break
    return rows


class EmResearchAdapter:
    name = "em"

    def __init__(self) -> None:
        try:
            _load_akshare()
            self.mode = "live"
        except RuntimeError:
            self.mode = "stub"

    def fetch_research_reports(self, stock_codes: list[str], limit: int = 20) -> list[dict]:
        rows: list[dict] = []
        for raw_code in stock_codes:
            code = normalize_display_code(raw_code)
            if not is_real_a_share_code(code):
                continue
            try:
                rows.extend(_fetch_one(code, limit))
            except Exception as exc:
                logger.warning("东财研报拉取 %s 失败: %s", code, exc)
        return rows
