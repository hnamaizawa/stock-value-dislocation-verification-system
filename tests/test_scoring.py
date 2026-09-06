import pandas as pd

from value_dislocation.strategy.scoring import score_candidates


def test_score_is_bounded():
    df = pd.DataFrame(
        [
            {
                "sales_cagr_3y": 0.05,
                "operating_margin": 0.10,
                "operating_cf_positive_ratio_3y": 1.0,
                "equity_ratio": 0.55,
                "forecast_op_growth": 0.10,
                "per_vs_sector": 0.75,
                "pbr_vs_sector": 0.80,
                "drawdown_52w": -0.30,
                "relative_return_6m": -0.18,
                "externality": 0.9,
                "temporary_probability": 0.8,
                "catalyst_probability": 0.7,
                "operating_profit_latest": 100,
                "review_status": "approved",
                "source_url": "https://example.com",
            }
        ]
    )
    out = score_candidates(df)
    assert 0 <= out.iloc[0]["score"] <= 100
    assert out.iloc[0]["penalty"] == 0
