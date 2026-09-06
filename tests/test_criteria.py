from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd

from value_dislocation.strategy.criteria import build_quantitative_table, screening_funnel
from value_dislocation.strategy.features import price_features


def _config() -> dict:
    return {
        "universe": {
            "allowed_markets": ["Prime"],
            "min_average_turnover_yen_20d": 1_000_000,
            "min_price_yen": 100,
        },
        "screen": {
            "minimum_equity_ratio": 0.30,
            "minimum_operating_cf_positive_ratio_3y": 2 / 3,
            "minimum_sales_cagr_3y": -0.05,
            "minimum_operating_margin": 0.0,
            "require_sales_history": False,
            "maximum_forecast_op_decline": -0.20,
            "require_forecast": False,
            "minimum_drawdown_52w": -0.18,
            "minimum_relative_underperformance_6m": -0.08,
            "relative_filter_when_topix_missing": "skip_with_warning",
            "quantitative_min_score": 0,
            "max_review_queue": 50,
        },
    }


def _companies() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "code": ["11110"],
            "name": ["Test Company"],
            "sector": ["Services"],
            "market": ["Prime"],
            "shares_outstanding": [10_000_000],
        }
    )


def _prices(with_topix: bool) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=260)
    close = np.linspace(1500.0, 1000.0, len(dates))
    data = {
        "date": dates,
        "code": ["11110"] * len(dates),
        "open": close,
        "high": np.maximum(close, 1500.0),
        "low": close - 10,
        "close": close,
        "volume": [100_000] * len(dates),
        "turnover_yen": close * 100_000,
    }
    if with_topix:
        data["topix_close"] = np.linspace(2500.0, 2700.0, len(dates))
    return pd.DataFrame(data)


def _financials() -> pd.DataFrame:
    rows = []
    for year, sales, op, cfo in [
        (2023, 1_000_000, 100_000, 90_000),
        (2024, 1_020_000, 102_000, -10_000),
        (2025, 1_040_000, 104_000, 100_000),
    ]:
        rows.append(
            {
                "code": "11110",
                "disclosure_date": pd.Timestamp(f"{year + 1}-05-10"),
                "period_end": pd.Timestamp(f"{year}-03-31"),
                "fiscal_year": year,
                "is_full_year_actual": True,
                "sales": sales,
                "operating_profit": op,
                "operating_cf": cfo,
                "total_assets": 2_000_000,
                "equity": 1_000_000,
                "cash": 200_000,
                "interest_bearing_debt": np.nan,
                "eps": 100.0,
                "book_value_per_share": 500.0,
                "forecast_operating_profit": 110_000,
            }
        )
    return pd.DataFrame(rows)


def test_topix_missing_is_not_replaced_by_security_return():
    prices = _prices(with_topix=False)
    as_of = prices["date"].max()
    features = price_features(prices, as_of)
    assert pd.isna(features.loc[0, "relative_return_6m"])
    assert not bool(features.loc[0, "topix_available"])


def test_missing_topix_skips_relative_hard_filter_with_explicit_warning():
    prices = _prices(with_topix=False)
    table = build_quantitative_table(
        _companies(), prices, _financials(), prices["date"].max(), _config()
    )
    row = table.iloc[0]
    assert bool(row["pass_relative_underperformance"])
    assert not bool(row["relative_filter_applied"])
    assert "利用できず" in row["warning_reasons"]
    assert pd.isna(row["relative_return_6m"])


def test_topix_relative_filter_is_applied_when_available():
    prices = _prices(with_topix=True)
    table = build_quantitative_table(
        _companies(), prices, _financials(), prices["date"].max(), _config()
    )
    row = table.iloc[0]
    assert bool(row["relative_filter_applied"])
    assert not pd.isna(row["relative_return_6m"])


def test_funnel_is_monotonic():
    prices = _prices(with_topix=False)
    table = build_quantitative_table(
        _companies(), prices, _financials(), prices["date"].max(), _config()
    )
    counts = [int(item["count"]) for item in screening_funnel(table)]
    assert counts == sorted(counts, reverse=True)


def test_etf_proxy_is_used_when_official_topix_is_missing():
    prices = _prices(with_topix=False)
    prices["topix_proxy_close"] = np.linspace(2500.0, 2600.0, len(prices))
    prices["topix_proxy_code"] = "13060"
    prices["topix_proxy_label"] = "NEXT FUNDS TOPIX連動型上場投信 (1306)"
    table = build_quantitative_table(_companies(), prices, _financials(), prices["date"].max(), _config())
    row = table.iloc[0]
    assert bool(row["topix_proxy_available"])
    assert bool(row["relative_filter_applied"])
    assert row["benchmark_source"] == "topix_etf_proxy"
    assert not pd.isna(row["relative_return_6m"])


def test_official_topix_has_priority_over_etf_proxy_in_auto_mode():
    prices = _prices(with_topix=True)
    prices["topix_proxy_close"] = np.linspace(2500.0, 2200.0, len(prices))
    prices["topix_proxy_code"] = "13060"
    prices["topix_proxy_label"] = "NEXT FUNDS TOPIX連動型上場投信 (1306)"
    table = build_quantitative_table(_companies(), prices, _financials(), prices["date"].max(), _config())
    assert table.iloc[0]["benchmark_source"] == "official_topix"
