"""临时脚本：测试 Tushare Pro 连接并拉取 003031 当日行情。

用法:
    cd backend
    $env:TUSHARE_TOKEN="你的token"; python scripts/test_tushare_003031.py
"""
from __future__ import annotations

import json
import os
import sys

for key in list(os.environ.keys()):
    if "proxy" in key.lower():
        del os.environ[key]
os.environ["NO_PROXY"] = "*"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TOKEN = os.getenv("TUSHARE_TOKEN", "")
CODE = "003031"
EXPECTED_CLOSE = 195.57


def main() -> None:
    if not TOKEN:
        print("未设置 TUSHARE_TOKEN")
        return

    import tushare as ts

    pro = ts.pro_api(TOKEN)

    print("=== 1) 连接测试 pro.daily(003031.SZ) ===")
    try:
        df = pro.daily(ts_code="003031.SZ", start_date="20260610", end_date="20260625",
                       fields="trade_date,close")
        print(df.to_string())
    except Exception as exc:
        print(f"daily 失败: {exc}")

    print("\n=== 2) 适配器 fetch_market_rows(['003031']) ===")
    from app.adapters.market.tushare_provider import fetch_market_rows

    rows = fetch_market_rows([CODE])
    print(json.dumps(rows, ensure_ascii=False, indent=2))

    if rows:
        close = rows[0].get("close_price")
        ok = close is not None and abs(close - EXPECTED_CLOSE) < 0.01
        verdict = "一致" if ok else "不一致(请在你本机核对，沙箱数据可能不同)"
        print(f"\n收盘价={close} 期望={EXPECTED_CLOSE} -> {verdict}")


if __name__ == "__main__":
    main()
