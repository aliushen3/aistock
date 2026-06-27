"""Mock 板块成分股适配器 — 返回真实格式的 A 股代码供测试。"""

from __future__ import annotations


class MockConstituentAdapter:
    name = "mock"
    mode = "stub"

    def fetch_board_constituents(self, board_type: str, board_name: str) -> list[dict]:
        return [
            {
                "stock_code": "601138",
                "name": "工业富联",
                "market_cap_billion": 4500.0,
                "board_type": board_type,
                "board_name": board_name,
            },
            {
                "stock_code": "300308",
                "name": "中际旭创",
                "market_cap_billion": 1200.0,
                "board_type": board_type,
                "board_name": board_name,
            },
            {
                "stock_code": "002463",
                "name": "沪电股份",
                "market_cap_billion": 800.0,
                "board_type": board_type,
                "board_name": board_name,
            },
        ]
