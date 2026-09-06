from __future__ import annotations

import numpy as np
import pandas as pd

from value_dislocation.strategy.criteria import (
    apply_quantitative_criteria,
    screening_funnel,
    shortlist_from_table,
)
from value_dislocation.strategy.features import price_features


def _prepared() -> pd.DataFrame:
    common = {
        "market": "Prime",
        "close": 1000.0,
        "drawdown_52w": -0.05,
        "return_6m": 0.02,
        "topix_available": False,
        "topix_proxy_available": False,
        "relative_return_6m": np.nan,
        "equity_ratio": 0.10,  # deliberately weak: active-trading mode must not require it
        "operating_profit_latest": -1.0,
        "operating_cf_positive_ratio_3y": 0.0,
        "sales_cagr_3y": -0.50,
        "operating_margin": -0.20,
        "forecast_op_growth": -0.80,
        "dividend_data_available": False,
        "forecast_annual_dividend_per_share": np.nan,
        "forecast_dividend_yield": np.nan,
        "payout_ratio": np.nan,
        "forecast_dividend_change_rate": np.nan,
        "financial_history_years": 1,
        "quantitative_score": 5.0,
    }
    return pd.DataFrame([
        {
            **common,
            "code": "11110",
            "name": "Active",
            "average_turnover_yen_20d": 800_000_000.0,
            "volatility_60d": 0.65,
            "average_intraday_range_20d": 0.045,
            "average_absolute_return_20d": 0.025,
        },
        {
            **common,
            "code": "22220",
            "name": "Calm",
            "average_turnover_yen_20d": 900_000_000.0,
            "volatility_60d": 0.18,
            "average_intraday_range_20d": 0.012,
            "average_absolute_return_20d": 0.006,
        },
    ])


def _active_config() -> dict:
    return {
        "universe": {
            "allowed_markets": ["Prime"],
            "min_average_turnover_yen_20d": 100_000_000,
            "min_price_yen": 100,
        },
        "screen": {
            "selection_strategy": "active_trading",
            "minimum_volatility_60d": 0.35,
            "minimum_average_intraday_range_20d": 0.025,
            "minimum_daytrade_activity_score": 0,
            "minimum_equity_ratio": 0.40,
            "minimum_operating_cf_positive_ratio_3y": 1.0,
            "minimum_sales_cagr_3y": 0.10,
            "minimum_operating_margin": 0.10,
            "require_sales_history": True,
            "maximum_forecast_op_decline": -0.10,
            "require_forecast": True,
            "minimum_drawdown_52w": -0.20,
            "minimum_relative_underperformance_6m": -0.10,
            "relative_filter_when_topix_missing": "skip_with_warning",
            "use_relative_underperformance_filter": True,
            "market_benchmark_mode": "auto",
            "quantitative_min_score": 80,
            "max_review_queue": 50,
            "require_dividend": True,
            "minimum_annual_dividend_per_share": 1.0,
            "minimum_forecast_dividend_yield": 0.03,
            "maximum_forecast_dividend_yield": 0.08,
            "maximum_payout_ratio": 0.60,
            "exclude_forecast_dividend_cut": True,
        },
    }


def test_active_trading_selects_high_movement_even_when_value_filters_fail():
    table = apply_quantitative_criteria(_prepared(), _active_config())
    selected = table.set_index("code")["selected_for_review"].to_dict()
    assert bool(selected["11110"])
    assert not bool(selected["22220"])
    assert not bool(table.loc[table["code"] == "11110", "hard_filter_pass"].iloc[0])


def test_active_trading_shortlist_and_funnel_use_activity_score():
    config = _active_config()
    table = apply_quantitative_criteria(_prepared(), config)
    shortlist = shortlist_from_table(table, config)
    assert shortlist["code"].tolist() == ["11110"]
    stages = [item["stage"] for item in screening_funnel(table)]
    assert stages == [
        "価格データが揃う銘柄",
        "市場・流動性・株価",
        "60日ボラティリティ",
        "20日平均日中値幅",
        "値動き活発度",
    ]


def test_price_features_include_intraday_movement_metrics():
    dates = pd.bdate_range("2026-01-05", periods=80)
    close = pd.Series([1000 + (50 if i % 2 else -50) for i in range(len(dates))], dtype=float)
    prices = pd.DataFrame({
        "date": dates,
        "code": ["11110"] * len(dates),
        "open": close,
        "high": close * 1.03,
        "low": close * 0.97,
        "close": close,
        "volume": [500_000] * len(dates),
        "turnover_yen": close * 500_000,
    })
    features = price_features(prices, dates.max()).iloc[0]
    assert features["volatility_60d"] > 0
    assert 0.05 < features["average_intraday_range_20d"] < 0.07
    assert features["average_absolute_return_20d"] > 0


def test_selection_strategy_never_imports_or_calls_jquants():
    from pathlib import Path
    source = Path("src/value_dislocation/strategy/criteria.py").read_text(encoding="utf-8")
    assert "jquants" not in source.lower()
    assert "fetch_and_curate" not in source
