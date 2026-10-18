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


def test_quantitative_score_excludes_review_penalties_but_keeps_financial_penalties():
    df = pd.DataFrame([{
        "sales_cagr_3y": 0.05, "operating_margin": 0.10,
        "operating_cf_positive_ratio_3y": 1.0, "equity_ratio": 0.55,
        "forecast_op_growth": 0.10, "per_vs_sector": 0.75,
        "pbr_vs_sector": 0.80, "drawdown_52w": -0.30,
        "relative_return_6m": -0.18, "operating_profit_latest": 100,
        "review_status": "pending", "source_url": "",
    }])
    scored = score_candidates(df).iloc[0]
    assert scored["quantitative_score"] == scored["quality_score"] + scored["valuation_score"] + scored["dislocation_score"]
    assert scored["review_penalty"] == 28
    assert scored["score"] < scored["quantitative_score"]


def test_external_explained_mode_weights_decline_points_by_attribution():
    base = {
        "drawdown_52w": -0.30, "relative_return_6m": -0.18,
        "operating_profit_latest": 100, "review_status": "approved", "source_url": "url",
        "external_shock_attribution_v2": 1.0,
    }
    full = score_candidates(pd.DataFrame([base]), dislocation_score_mode="external_explained").iloc[0]
    half = score_candidates(pd.DataFrame([{**base, "external_shock_attribution_v2": 0.5}]), dislocation_score_mode="external_explained").iloc[0]
    legacy = score_candidates(pd.DataFrame([{**base, "external_shock_attribution_v2": 0.0}])).iloc[0]
    assert full["dislocation_score"] > half["dislocation_score"]
    assert half["dislocation_score"] > 0
    assert legacy["dislocation_score"] > half["dislocation_score"]


def test_external_explained_missing_attribution_half_or_zero():
    df = pd.DataFrame([{
        "drawdown_52w": -0.30, "relative_return_6m": -0.18,
        "operating_profit_latest": 100, "review_status": "approved", "source_url": "url",
        "external_shock_attribution_v2": float("nan"),
    }])
    half = score_candidates(df, dislocation_score_mode="external_explained", attribution_missing_policy="half").iloc[0]
    zero = score_candidates(df, dislocation_score_mode="external_explained", attribution_missing_policy="zero").iloc[0]
    assert half["dislocation_score"] > zero["dislocation_score"] == 0
    assert half["quantitative_score"] <= 85
