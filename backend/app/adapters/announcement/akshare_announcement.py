"""AkShare 巨潮公告适配器 — stock_zh_a_disclosure_report_cninfo（免费）。

走 cninfo.com.cn，与东方财富不同源；输出对齐 ods_announcement。
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone

from app.adapters.market._net import ensure_ipv4, with_retry
from app.adapters.market._utils import is_real_a_share_code, normalize_display_code
from app.config import ANNOUNCEMENT_LOOKBACK_DAYS

logger = logging.getLogger(__name__)

_CN_TZ = timezone(timedelta(hours=8))

_CATEGORY_KEYWORDS = {
    "capacity_expansion": ("扩产", "募投", "投建", "产能", "扩建"),
    "earnings": ("业绩", "年报", "季报", "中报", "快报", "预增", "预减", "预告"),
    "shareholding": ("减持", "增持", "回购", "股份", "解禁"),
    "restructuring": ("重组", "收购", "并购", "重大资产"),
    "risk": ("风险", "问询", "处罚", "立案", "诉讼", "ST"),
}


def _load_akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("未安装 akshare，请 pip install akshare") from exc
    return ak


def _classify(title: str) -> str:
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(k in title for k in keywords):
            return category
    return "general"


def _ann_id(code: str, raw_id, title: str, date: str) -> str:
    if raw_id not in (None, "", "nan"):
        return f"cninfo_{raw_id}"
    digest = hashlib.md5(f"{code}|{title}|{date}".encode("utf-8")).hexdigest()[:12]
    return f"cninfo_{code}_{digest}"


def _fetch_one(code: str, start_date: str, end_date: str, limit: int) -> list[dict]:
    ak = _load_akshare()
    ensure_ipv4()
    df = with_retry(
        lambda: ak.stock_zh_a_disclosure_report_cninfo(
            symbol=code, market="沪深京", start_date=start_date, end_date=end_date
        ),
        label=f"cninfo ann {code}",
    )
    if df is None or getattr(df, "empty", True):
        return []
    rows: list[dict] = []
    for _, r in df.iterrows():
        title = str(r.get("公告标题", "") or "")
        if not title:
            continue
        date_raw = str(r.get("公告时间", "") or "")
        ann_date = date_raw[:10]
        raw_id = r.get("announcementId")
        rows.append(
            {
                "ann_id": _ann_id(code, raw_id, title, ann_date),
                "stock_code": code,
                "title": title[:512],
                "ann_date": ann_date,
                "category": _classify(title),
                "url": str(r.get("公告链接", "") or "") or None,
            }
        )
        if len(rows) >= limit:
            break
    return rows


class AkshareAnnouncementAdapter:
    name = "akshare"

    def __init__(self) -> None:
        try:
            _load_akshare()
            self.mode = "live"
        except RuntimeError:
            self.mode = "stub"

    def fetch_announcements(self, stock_codes: list[str], limit: int = 20) -> list[dict]:
        today = datetime.now(_CN_TZ)
        start = (today - timedelta(days=ANNOUNCEMENT_LOOKBACK_DAYS)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        rows: list[dict] = []
        for raw_code in stock_codes:
            code = normalize_display_code(raw_code)
            if not is_real_a_share_code(code):
                continue
            try:
                rows.extend(_fetch_one(code, start, end, limit))
            except Exception as exc:
                logger.warning("巨潮公告拉取 %s 失败: %s", code, exc)
        return rows
