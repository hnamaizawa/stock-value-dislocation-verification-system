import pandas as pd

from value_dislocation.risk import create_order_proposals


def test_orders_respect_total_capital_limit():
    candidates = pd.DataFrame(
        [
            {
                "code": "12340",
                "name": "テスト",
                "sector": "食品",
                "close": 1000,
                "score": 80,
                "category": "原材料高",
                "evidence": "一時要因",
                "source_url": "https://example.com",
            }
        ]
    )
    cfg = {
        "trading_capital_yen": 3_000_000,
        "max_total_invested_ratio": 0.60,
        "max_positions": 6,
        "max_position_ratio": 0.10,
        "risk_per_position_ratio": 0.008,
        "catastrophic_stop_pct": 0.22,
        "take_profit_pct": 0.35,
        "board_lot": 100,
        "entry_tranches": [
            {"weight": 0.4, "discount_from_close": 0.02},
            {"weight": 0.3, "discount_from_close": 0.07},
            {"weight": 0.3, "discount_from_close": 0.12},
        ],
    }
    out = create_order_proposals(candidates, cfg)
    assert out["estimated_amount"].sum() <= 1_800_000
    assert set(out["approval_status"]) == {"未承認"}
