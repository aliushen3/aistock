from __future__ import annotations

from app.services.a_share_data_source import fetch_cninfo_announcements


class DirectCninfoAnnouncementAdapter:
    name = "cninfo_direct"
    mode = "live"

    def fetch_announcements(self, stock_codes: list[str], limit: int = 20) -> list[dict]:
        rows: list[dict] = []
        for code in stock_codes:
            rows.extend(fetch_cninfo_announcements(code, page_size=limit))
        return rows
