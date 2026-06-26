"""临时脚本：测试 AkShare 单股拉取 003031 当日行情。

用法（在能访问东方财富的机器上）:
    cd backend
    python scripts/test_akshare_003031.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adapters.market.akshare_provider import fetch_market_rows

CODE = "003031"


def main() -> None:
    print(f"=== 适配器单股拉取 fetch_market_rows(['{CODE}']) ===")
    try:
        rows = fetch_market_rows([CODE])
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"拉取失败: {exc}")


if __name__ == "__main__":
    main()
