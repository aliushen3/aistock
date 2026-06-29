from __future__ import annotations

import hashlib
import json
import math
import random
import re
import threading
import time
from functools import lru_cache
from typing import Any

import httpx

from app.adapters.market._utils import is_real_a_share_code, normalize_display_code

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
REPORT_API = "https://reportapi.eastmoney.com/report/list"
PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
EM_MIN_INTERVAL = 1.0

_EM_LOCK = threading.Lock()
_EM_LAST_CALL = 0.0


class AShareDataError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _http_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": UA},
        timeout=20.0,
        follow_redirects=True,
    )


def _normalize_code(code: str) -> str:
    normalized = normalize_display_code(code)
    if not is_real_a_share_code(normalized):
        raise AShareDataError(f"invalid stock code: {code}")
    return normalized


def _market_prefix(code: str) -> str:
    if code.startswith(("6", "9")):
        return "sh"
    if code.startswith("8"):
        return "bj"
    return "sz"


def _secid(code: str) -> str:
    return f"1.{code}" if code.startswith("6") else f"0.{code}"


def _sleep_for_eastmoney() -> None:
    global _EM_LAST_CALL
    with _EM_LOCK:
        wait = EM_MIN_INTERVAL - (time.time() - _EM_LAST_CALL)
        if wait > 0:
            time.sleep(wait + random.uniform(0.1, 0.3))
        _EM_LAST_CALL = time.time()


def _em_get(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> httpx.Response:
    _sleep_for_eastmoney()
    merged_headers = {"User-Agent": UA}
    if headers:
        merged_headers.update(headers)
    return _http_client().get(url, params=params, headers=merged_headers)


def _safe_float(value: Any) -> float | None:
    if value in (None, "", "-", "--", "nan", "None"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _parse_cn_number(value: Any) -> float | None:
    if value in (None, "", "-", "--", "nan", "None"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    multiplier = 1.0
    if text.endswith("亿"):
        multiplier = 100000000.0
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 10000.0
        text = text[:-1]
    elif text.endswith("%"):
        multiplier = 0.01
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def _report_key(code: str, title: str, report_date: str) -> str:
    digest = hashlib.md5(f"{code}|{title}|{report_date}".encode("utf-8")).hexdigest()[:16]
    return f"em_{code}_{digest}"


def _cninfo_date(ts: Any) -> str:
    if isinstance(ts, (int, float)):
        return time.strftime("%Y-%m-%d", time.localtime(ts / 1000))
    return str(ts)[:10] if ts else ""


def fetch_tencent_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    normalized = [_normalize_code(code) for code in codes]
    symbols = [_market_prefix(code) + code for code in normalized]
    url = "https://qt.gtimg.cn/q=" + ",".join(symbols)
    resp = _http_client().get(url)
    resp.raise_for_status()
    data = resp.content.decode("gbk", errors="ignore")

    result: dict[str, dict[str, Any]] = {}
    for line in data.strip().split(";"):
        if "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        values = line.split('"')[1].split("~")
        if len(values) < 53:
            continue
        code = key[2:]
        result[code] = {
            "name": values[1],
            "price": _safe_float(values[3]),
            "last_close": _safe_float(values[4]),
            "open": _safe_float(values[5]),
            "change_amt": _safe_float(values[31]),
            "change_pct": _safe_float(values[32]),
            "high": _safe_float(values[33]),
            "low": _safe_float(values[34]),
            "amount_wan": _safe_float(values[37]),
            "turnover_pct": _safe_float(values[38]),
            "pe_ttm": _safe_float(values[39]),
            "amplitude_pct": _safe_float(values[43]),
            "mcap_yi": _safe_float(values[44]),
            "float_mcap_yi": _safe_float(values[45]),
            "pb": _safe_float(values[46]),
            "limit_up": _safe_float(values[47]),
            "limit_down": _safe_float(values[48]),
            "vol_ratio": _safe_float(values[49]),
            "pe_static": _safe_float(values[52]),
        }
    return result


def fetch_eastmoney_reports(code: str, max_pages: int = 1) -> list[dict[str, Any]]:
    normalized = _normalize_code(code)
    rows: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": "*",
            "pageSize": "100",
            "industry": "*",
            "rating": "*",
            "ratingChange": "*",
            "beginTime": "2000-01-01",
            "endTime": "2030-01-01",
            "pageNo": str(page),
            "fields": "",
            "qType": "0",
            "orgCode": "",
            "code": normalized,
            "rcode": "",
            "p": str(page),
            "pageNum": str(page),
            "pageNumber": str(page),
        }
        resp = _em_get(REPORT_API, params=params, headers={"Referer": "https://data.eastmoney.com/"})
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("data") or []
        for item in batch:
            report_date = str(item.get("publishDate") or "")[:10]
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            rows.append(
                {
                    "report_key": _report_key(normalized, title, report_date),
                    "stock_code": normalized,
                    "title": title[:512],
                    "org_name": (item.get("orgSName") or None),
                    "rating": (item.get("emRatingName") or None),
                    "report_date": report_date or None,
                    "url": PDF_TPL.format(info_code=item.get("infoCode", "")) if item.get("infoCode") else None,
                    "info_code": item.get("infoCode"),
                    "predict_this_year_eps": _safe_float(item.get("predictThisYearEps")),
                    "predict_next_year_eps": _safe_float(item.get("predictNextYearEps")),
                    "predict_next_two_year_eps": _safe_float(item.get("predictNextTwoYearEps")),
                }
            )
        if not batch or page >= int(payload.get("TotalPage") or 1):
            break
    return rows


def build_report_consensus(reports: list[dict[str, Any]]) -> dict[str, Any]:
    current = [r["predict_this_year_eps"] for r in reports if r.get("predict_this_year_eps") and r["predict_this_year_eps"] > 0]
    next_year = [r["predict_next_year_eps"] for r in reports if r.get("predict_next_year_eps") and r["predict_next_year_eps"] > 0]
    two_year = [r["predict_next_two_year_eps"] for r in reports if r.get("predict_next_two_year_eps") and r["predict_next_two_year_eps"] > 0]

    def _summary(values: list[float]) -> dict[str, Any] | None:
        if not values:
            return None
        return {
            "count": len(values),
            "min": round(min(values), 4),
            "avg": round(sum(values) / len(values), 4),
            "max": round(max(values), 4),
        }

    return {
        "this_year": _summary(current),
        "next_year": _summary(next_year),
        "next_two_year": _summary(two_year),
    }


def compute_valuation_snapshot(code: str) -> dict[str, Any]:
    normalized = _normalize_code(code)
    quotes = fetch_tencent_quotes([normalized]).get(normalized)
    if not quotes:
        raise AShareDataError(f"quote not found for {normalized}")
    reports = fetch_eastmoney_reports(normalized, max_pages=1)
    consensus = build_report_consensus(reports)

    result: dict[str, Any] = {
        "stock_code": normalized,
        "name": quotes.get("name"),
        "price": quotes.get("price"),
        "market": quotes,
        "consensus": consensus,
        "report_count": len(reports),
    }

    this_year = (consensus.get("this_year") or {}).get("avg")
    next_year = (consensus.get("next_year") or {}).get("avg")
    price = quotes.get("price")
    if price and this_year and this_year > 0:
        result["forward_pe"] = round(price / this_year, 2)
    else:
        result["forward_pe"] = None

    if this_year and next_year and this_year > 0 and next_year > 0:
        cagr = next_year / this_year - 1
        result["eps_growth_next_year_pct"] = round(cagr * 100, 2)
        if result["forward_pe"] and cagr > 0:
            result["peg"] = round(result["forward_pe"] / (cagr * 100), 2)
        else:
            result["peg"] = None
        if result["forward_pe"] and result["forward_pe"] > 30 and cagr > 0:
            result["pe_digestion_years"] = round(math.log(result["forward_pe"] / 30) / math.log(1 + cagr), 2)
        else:
            result["pe_digestion_years"] = 0.0
    else:
        result["eps_growth_next_year_pct"] = None
        result["peg"] = None
        result["pe_digestion_years"] = None
    return result


@lru_cache(maxsize=1)
def _cninfo_orgid_map() -> dict[str, str]:
    resp = _http_client().get(
        "http://www.cninfo.com.cn/new/data/szse_stock.json",
        headers={"User-Agent": UA},
    )
    resp.raise_for_status()
    payload = resp.json()
    return {item["code"]: item["orgId"] for item in payload.get("stockList", []) if item.get("code") and item.get("orgId")}


def _cninfo_orgid(code: str) -> str:
    normalized = _normalize_code(code)
    orgid = _cninfo_orgid_map().get(normalized)
    if orgid:
        return orgid
    if normalized.startswith("6"):
        return f"gssh0{normalized}"
    if normalized.startswith(("8", "4")):
        return f"gsbj0{normalized}"
    return f"gssz0{normalized}"


def fetch_cninfo_announcements(code: str, page_size: int = 20) -> list[dict[str, Any]]:
    normalized = _normalize_code(code)
    payload = {
        "stock": f"{normalized},{_cninfo_orgid(normalized)}",
        "tabName": "fulltext",
        "pageSize": str(page_size),
        "pageNum": "1",
        "column": "",
        "category": "",
        "plate": "",
        "seDate": "",
        "searchkey": "",
        "secid": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    resp = _http_client().post(
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        data=payload,
        headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.cninfo.com.cn/new/disclosure",
            "Origin": "https://www.cninfo.com.cn",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    rows: list[dict[str, Any]] = []
    for item in data.get("announcements") or []:
        ann_id = item.get("announcementId")
        rows.append(
            {
                "ann_id": f"cninfo_{ann_id}" if ann_id else f"cninfo_{normalized}_{len(rows)}",
                "stock_code": normalized,
                "title": item.get("announcementTitle", "")[:512],
                "ann_date": _cninfo_date(item.get("announcementTime")),
                "category": item.get("announcementTypeName") or "general",
                "url": f"https://www.cninfo.com.cn/new/disclosure/detail?annoId={ann_id}" if ann_id else None,
            }
        )
    return rows


def fetch_sina_financial_report(code: str, report_type: str = "lrb", num: int = 8) -> list[dict[str, Any]]:
    normalized = _normalize_code(code)
    paper_code = f"{_market_prefix(normalized)}{normalized}"
    resp = _http_client().get(
        "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022",
        params={
            "paperCode": paper_code,
            "source": report_type,
            "type": "0",
            "page": "1",
            "num": str(num),
        },
        headers={"User-Agent": UA},
    )
    resp.raise_for_status()
    report_list = resp.json().get("result", {}).get("data", {}).get("report_list", {}) or {}
    rows: list[dict[str, Any]] = []
    for period in sorted(report_list.keys(), reverse=True)[:num]:
        record = {"report_period": f"{period[:4]}-{period[4:6]}-{period[6:8]}"}
        for item in report_list.get(period, {}).get("data", []) or []:
            title = item.get("item_title")
            if not title or item.get("item_value") is None:
                continue
            record[title] = item.get("item_value")
            if item.get("item_tongbi") not in (None, ""):
                record[f"{title}_yoy"] = item.get("item_tongbi")
        rows.append(record)
    return rows


def build_financial_snapshot(code: str) -> dict[str, Any]:
    normalized = _normalize_code(code)
    rows = fetch_sina_financial_report(normalized, report_type="lrb", num=1)
    if not rows:
        return {"stock_code": normalized, "report_period": None}
    row = rows[0]
    revenue = _parse_cn_number(row.get("营业总收入") or row.get("营业收入"))
    net_profit = _parse_cn_number(row.get("净利润"))
    gross_margin = _parse_cn_number(row.get("销售毛利率") or row.get("毛利率"))
    roe = _parse_cn_number(row.get("净资产收益率") or row.get("ROE"))
    eps = _parse_cn_number(row.get("基本每股收益") or row.get("每股收益"))
    return {
        "stock_code": normalized,
        "report_period": row.get("report_period"),
        "revenue": revenue,
        "net_profit": net_profit,
        "gross_margin": gross_margin,
        "roe": roe,
        "eps": eps,
        "raw": row,
    }


def fetch_eastmoney_stock_info(code: str) -> dict[str, Any]:
    normalized = _normalize_code(code)
    resp = _em_get(
        "https://push2.eastmoney.com/api/qt/stock/get",
        params={
            "fltt": "2",
            "invt": "2",
            "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
            "secid": _secid(normalized),
        },
    )
    resp.raise_for_status()
    data = resp.json().get("data", {})
    price = _safe_float(data.get("f43"))
    if price is not None and price > 1000:
        price = round(price / 100, 2)
    return {
        "code": data.get("f57") or normalized,
        "name": data.get("f58"),
        "industry": data.get("f127"),
        "total_shares": data.get("f84"),
        "float_shares": data.get("f85"),
        "mcap": data.get("f116"),
        "float_mcap": data.get("f117"),
        "list_date": str(data.get("f189") or ""),
        "price": price,
    }


def fetch_eastmoney_concept_blocks(code: str) -> dict[str, Any]:
    normalized = _normalize_code(code)
    resp = _em_get(
        "https://push2.eastmoney.com/api/qt/slist/get",
        params={
            "fltt": "2",
            "invt": "2",
            "secid": _secid(normalized),
            "spt": "3",
            "pi": "0",
            "pz": "200",
            "po": "1",
            "fields": "f12,f14,f3,f128",
        },
        headers={"Referer": "https://quote.eastmoney.com/"},
    )
    resp.raise_for_status()
    diff = (resp.json().get("data") or {}).get("diff") or {}
    items = diff.values() if isinstance(diff, dict) else diff
    boards = [
        {
            "name": item.get("f14", ""),
            "code": item.get("f12", ""),
            "change_pct": item.get("f3"),
            "lead_stock": item.get("f128", ""),
        }
        for item in items
    ]
    return {"total": len(boards), "boards": boards, "concept_tags": [item["name"] for item in boards]}


def fetch_eastmoney_fund_flow_minute(code: str) -> list[dict[str, Any]]:
    normalized = _normalize_code(code)
    resp = _em_get(
        "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get",
        params={
            "secid": _secid(normalized),
            "klt": 1,
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
        },
        headers={
            "Referer": "https://quote.eastmoney.com/",
            "Origin": "https://quote.eastmoney.com",
        },
    )
    resp.raise_for_status()
    rows: list[dict[str, Any]] = []
    for line in resp.json().get("data", {}).get("klines", []) or []:
        parts = line.split(",")
        if len(parts) >= 6:
            rows.append(
                {
                    "time": parts[0],
                    "main_net": _safe_float(parts[1]) or 0.0,
                    "small_net": _safe_float(parts[2]) or 0.0,
                    "mid_net": _safe_float(parts[3]) or 0.0,
                    "large_net": _safe_float(parts[4]) or 0.0,
                    "super_net": _safe_float(parts[5]) or 0.0,
                }
            )
    return rows


def fetch_eastmoney_datacenter(
    report_name: str,
    columns: str = "ALL",
    filter_str: str = "",
    page_size: int = 50,
    sort_columns: str = "",
    sort_types: str = "-1",
) -> list[dict[str, Any]]:
    params = {
        "reportName": report_name,
        "columns": columns,
        "filter": filter_str,
        "pageNumber": "1",
        "pageSize": str(page_size),
        "sortColumns": sort_columns,
        "sortTypes": sort_types,
        "source": "WEB",
        "client": "WEB",
    }
    resp = _em_get(DATACENTER_URL, params=params)
    resp.raise_for_status()
    payload = resp.json()
    result = payload.get("result") or {}
    return result.get("data") or []


def fetch_eastmoney_industry_reports(
    industry_code: str = "*",
    max_pages: int = 1,
    begin: str = "2024-01-01",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": industry_code,
            "pageSize": "100",
            "industry": "*",
            "rating": "*",
            "ratingChange": "*",
            "beginTime": begin,
            "endTime": "2030-01-01",
            "pageNo": str(page),
            "fields": "",
            "qType": "1",
            "p": str(page),
            "pageNum": str(page),
            "pageNumber": str(page),
        }
        resp = _em_get(REPORT_API, params=params, headers={"Referer": "https://data.eastmoney.com/"})
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("data") or []
        for item in batch:
            report_date = str(item.get("publishDate") or "")[:10]
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            rows.append(
                {
                    "report_key": _report_key(
                        str(item.get("industryCode") or industry_code),
                        title,
                        report_date,
                    ),
                    "industry_code": item.get("industryCode"),
                    "industry_name": item.get("industryName"),
                    "title": title[:512],
                    "org_name": item.get("orgSName"),
                    "rating": item.get("emRatingName"),
                    "report_date": report_date or None,
                    "url": PDF_TPL.format(info_code=item.get("infoCode", "")) if item.get("infoCode") else None,
                }
            )
        if not batch or page >= int(payload.get("TotalPage") or 1):
            break
    return rows


def fetch_ths_hot_reason(trade_date: str | None = None) -> list[dict[str, Any]]:
    if trade_date is None:
        trade_date = time.strftime("%Y-%m-%d")
    url = (
        f"http://zx.10jqka.com.cn/event/api/getharden/"
        f"date/{trade_date}/orderby/date/orderway/desc/charset/GBK/"
    )
    resp = _http_client().get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "Chrome/117.0.0.0 Safari/537.36"
            )
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("errocode", 0) != 0:
        raise AShareDataError(payload.get("errormsg") or "ths hot reason failed")
    rows: list[dict[str, Any]] = []
    for item in payload.get("data") or []:
        rows.append(
            {
                "code": item.get("code"),
                "name": item.get("name"),
                "reason": item.get("reason"),
                "change_pct": _safe_float(item.get("zhangfu")),
                "turnover_pct": _safe_float(item.get("huanshou")),
                "close": _safe_float(item.get("close")),
                "market": item.get("market"),
            }
        )
    return rows


def fetch_industry_comparison(top_n: int = 20) -> dict[str, Any]:
    resp = _em_get(
        "https://push2.eastmoney.com/api/qt/clist/get",
        params={
            "pn": "1",
            "pz": "100",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fs": "m:90+t:2",
            "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
        },
        headers={"Referer": "https://quote.eastmoney.com/"},
    )
    resp.raise_for_status()
    diff = (resp.json().get("data") or {}).get("diff") or []
    items = list(diff.values()) if isinstance(diff, dict) else diff
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        rows.append(
            {
                "rank": idx + 1,
                "name": item.get("f14", ""),
                "change_pct": item.get("f3"),
                "code": item.get("f12", ""),
                "up_count": item.get("f104", 0),
                "down_count": item.get("f105", 0),
                "leader": item.get("f140", ""),
                "leader_change": item.get("f136", 0),
            }
        )
    return {
        "top": rows[:top_n],
        "bottom": rows[-top_n:] if top_n else [],
        "total": len(rows),
    }


def fetch_daily_dragon_tiger(trade_date: str | None = None, min_net_buy: float | None = None) -> dict[str, Any]:
    if trade_date is None:
        trade_date = time.strftime("%Y-%m-%d")
    data = fetch_eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')",
        page_size=500,
        sort_columns="BILLBOARD_NET_AMT",
        sort_types="-1",
    )
    if not data:
        return {"date": trade_date, "total_records": 0, "stocks": []}
    actual_date = str(data[0].get("TRADE_DATE", ""))[:10] or trade_date
    stocks: list[dict[str, Any]] = []
    for row in data:
        net_buy = (row.get("BILLBOARD_NET_AMT") or 0) / 10000
        if min_net_buy is not None and net_buy < min_net_buy:
            continue
        stocks.append(
            {
                "code": row.get("SECURITY_CODE", ""),
                "name": row.get("SECURITY_NAME_ABBR", ""),
                "reason": row.get("EXPLANATION", ""),
                "close": row.get("CLOSE_PRICE"),
                "change_pct": _safe_float(row.get("CHANGE_RATE")),
                "net_buy_wan": round(net_buy, 2),
                "turnover_pct": _safe_float(row.get("TURNOVERRATE")),
            }
        )
    return {"date": actual_date, "total_records": len(stocks), "stocks": stocks}


def fetch_dragon_tiger_board(code: str, trade_date: str | None = None, look_back: int = 30) -> dict[str, Any]:
    normalized = _normalize_code(code)
    if trade_date is None:
        trade_date = time.strftime("%Y-%m-%d")
    start_ts = time.mktime(time.strptime(trade_date, "%Y-%m-%d")) - look_back * 86400
    start_str = time.strftime("%Y-%m-%d", time.localtime(start_ts))
    data = fetch_eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=(
            f"(TRADE_DATE>='{start_str}')(TRADE_DATE<='{trade_date}')"
            f'(SECURITY_CODE="{normalized}")'
        ),
        page_size=50,
        sort_columns="TRADE_DATE",
        sort_types="-1",
    )
    records: list[dict[str, Any]] = []
    for row in data:
        records.append(
            {
                "date": str(row.get("TRADE_DATE", ""))[:10],
                "reason": row.get("EXPLANATION", ""),
                "net_buy_wan": round((row.get("BILLBOARD_NET_AMT") or 0) / 10000, 2),
                "turnover_pct": _safe_float(row.get("TURNOVERRATE")),
            }
        )
    return {"stock_code": normalized, "records": records}


def fetch_eastmoney_stock_news(code: str, page_size: int = 20) -> list[dict[str, Any]]:
    normalized = _normalize_code(code)
    inner_params = json.dumps(
        {
            "uid": "",
            "keyword": normalized,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": 1,
                    "pageSize": page_size,
                    "preTag": "",
                    "postTag": "",
                }
            },
        },
        separators=(",", ":"),
    )
    resp = _em_get(
        "https://search-api-web.eastmoney.com/search/jsonp",
        params={"cb": "jQuery_news", "param": inner_params},
        headers={"Referer": "https://so.eastmoney.com/"},
    )
    resp.raise_for_status()
    text = resp.text
    start = text.find("(")
    end = text.rfind(")")
    if start < 0 or end <= start:
        return []
    payload = json.loads(text[start + 1 : end])
    rows: list[dict[str, Any]] = []
    for item in payload.get("result", {}).get("cmsArticleWebOld", []) or []:
        title = re.sub(r"<[^>]+>", "", item.get("title", ""))
        content = re.sub(r"<[^>]+>", "", item.get("content", ""))[:200]
        rows.append(
            {
                "title": title,
                "content": content,
                "time": item.get("date", ""),
                "source": item.get("mediaName", ""),
                "url": item.get("url", ""),
            }
        )
    return rows


def fetch_eastmoney_global_news(page_size: int = 20) -> list[dict[str, Any]]:
    resp = _em_get(
        "https://np-weblist.eastmoney.com/comm/web/getFastNewsList",
        params={
            "client": "web",
            "biz": "web_724",
            "fastColumn": "102",
            "sortEnd": "",
            "pageSize": str(page_size),
            "req_trace": hashlib.md5(str(time.time()).encode("utf-8")).hexdigest(),
        },
        headers={"Referer": "https://kuaixun.eastmoney.com/"},
    )
    resp.raise_for_status()
    rows: list[dict[str, Any]] = []
    for item in resp.json().get("data", {}).get("fastNewsList", []) or []:
        rows.append(
            {
                "title": item.get("title", ""),
                "summary": (item.get("summary") or "")[:200],
                "time": item.get("showTime", ""),
            }
        )
    return rows


SEVEN_LAYER_CAPABILITIES = [
    {
        "layer": "market",
        "label": "行情层",
        "sources": ["tencent", "mootdx", "baidu"],
        "operations": ["quote", "valuation_snapshot"],
        "endpoint_count": 3,
        "ods_ready": True,
        "ods_adapter": "tencent",
    },
    {
        "layer": "research",
        "label": "研报层",
        "sources": ["eastmoney", "ths", "iwencai"],
        "operations": ["reports", "industry_reports", "consensus_snapshot"],
        "endpoint_count": 4,
        "ods_ready": True,
        "ods_adapter": "eastmoney",
    },
    {
        "layer": "signal",
        "label": "信号层",
        "sources": ["ths", "eastmoney"],
        "operations": [
            "ths_hot_reason",
            "concept_blocks",
            "fund_flow_minute",
            "dragon_tiger",
            "daily_dragon_tiger",
            "industry_ranking",
        ],
        "endpoint_count": 8,
        "ods_ready": False,
    },
    {
        "layer": "capital",
        "label": "资金面",
        "sources": ["eastmoney"],
        "operations": ["fund_flow_minute", "margin", "block_trade", "holder_count", "dividend"],
        "endpoint_count": 5,
        "ods_ready": False,
    },
    {
        "layer": "news",
        "label": "新闻层",
        "sources": ["eastmoney"],
        "operations": ["stock_news", "global_news"],
        "endpoint_count": 2,
        "ods_ready": False,
    },
    {
        "layer": "fundamental",
        "label": "基础数据",
        "sources": ["sina", "eastmoney", "mootdx"],
        "operations": ["financial_snapshot", "stock_info"],
        "endpoint_count": 4,
        "ods_ready": True,
        "ods_adapter": "sina",
    },
    {
        "layer": "announcement",
        "label": "公告层",
        "sources": ["cninfo", "mootdx"],
        "operations": ["announcements"],
        "endpoint_count": 2,
        "ods_ready": True,
        "ods_adapter": "cninfo_direct",
    },
]


def list_seven_layer_capabilities() -> list[dict[str, Any]]:
    return [dict(item) for item in SEVEN_LAYER_CAPABILITIES]


def route_task_to_layers(task: str) -> list[str]:
    mapping = {
        "valuation": ["market", "research", "fundamental"],
        "quote": ["market"],
        "research": ["research"],
        "signal": ["signal", "capital"],
        "news": ["news"],
        "fundamental": ["fundamental"],
        "announcement": ["announcement"],
        "sector_scan": ["signal", "research", "news"],
    }
    layers = mapping.get((task or "").lower())
    if not layers:
        raise AShareDataError(f"unsupported task: {task}")
    return layers


def fetch_layer_data(layer: str, stock_code: str | None = None, limit: int = 20) -> dict[str, Any]:
    layer = (layer or "").lower()
    if layer == "market":
        if not stock_code:
            raise AShareDataError("stock_code is required for market layer")
        normalized = _normalize_code(stock_code)
        return compute_valuation_snapshot(normalized)
    if layer == "research":
        if stock_code:
            normalized = _normalize_code(stock_code)
            reports = fetch_eastmoney_reports(normalized, max_pages=1)
            return {
                "stock_code": normalized,
                "reports": reports[:limit],
                "consensus": build_report_consensus(reports),
            }
        industry_reports = fetch_eastmoney_industry_reports(max_pages=1)
        return {"industry_reports": industry_reports[:limit]}
    if layer == "signal":
        payload: dict[str, Any] = {
            "ths_hot_reason": fetch_ths_hot_reason()[:limit],
            "industry_ranking": fetch_industry_comparison(top_n=min(limit, 20)),
            "daily_dragon_tiger": fetch_daily_dragon_tiger(),
        }
        if stock_code:
            normalized = _normalize_code(stock_code)
            payload["stock_code"] = normalized
            payload["concept_blocks"] = fetch_eastmoney_concept_blocks(normalized)
            payload["fund_flow_minute"] = fetch_eastmoney_fund_flow_minute(normalized)[:limit]
            payload["dragon_tiger"] = fetch_dragon_tiger_board(normalized)
        return payload
    if layer == "capital":
        if not stock_code:
            raise AShareDataError("stock_code is required for capital layer")
        normalized = _normalize_code(stock_code)
        return {
            "stock_code": normalized,
            "fund_flow_minute": fetch_eastmoney_fund_flow_minute(normalized)[:limit],
        }
    if layer == "news":
        payload = {"global_news": fetch_eastmoney_global_news(page_size=limit)}
        if stock_code:
            normalized = _normalize_code(stock_code)
            payload["stock_code"] = normalized
            payload["stock_news"] = fetch_eastmoney_stock_news(normalized, page_size=limit)
        return payload
    if layer == "fundamental":
        if not stock_code:
            raise AShareDataError("stock_code is required for fundamental layer")
        normalized = _normalize_code(stock_code)
        return {
            "stock_code": normalized,
            "stock_info": fetch_eastmoney_stock_info(normalized),
            "financial_snapshot": build_financial_snapshot(normalized),
        }
    if layer == "announcement":
        if not stock_code:
            raise AShareDataError("stock_code is required for announcement layer")
        normalized = _normalize_code(stock_code)
        return {"stock_code": normalized, "announcements": fetch_cninfo_announcements(normalized, page_size=limit)}
    raise AShareDataError(f"unsupported layer: {layer}")


def dumps_pretty(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)
