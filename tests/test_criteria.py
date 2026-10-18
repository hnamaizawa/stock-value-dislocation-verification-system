from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd

from value_dislocation.strategy.criteria import (
    apply_quantitative_criteria,
    build_quantitative_table,
    external_attribution_screen_comparison,
    screening_funnel,
)
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
    counts = [int(item["count"]) for item in screening_funnel(table) if not item.get("diagnostic")]
    assert counts == sorted(counts, reverse=True)


def _prepared_attribution_rows() -> pd.DataFrame:
    return pd.DataFrame({
        "code": ["A", "B", "C"], "name": ["A", "B", "C"],
        "market": ["Prime"] * 3, "sector": ["Tech"] * 3,
        "average_turnover_yen_20d": [5_000_000] * 3, "close": [500.0] * 3,
        "equity_ratio": [0.5] * 3, "operating_profit_latest": [100.0] * 3,
        "operating_cf_positive_ratio_3y": [1.0] * 3, "sales_cagr_3y": [0.1] * 3,
        "operating_margin": [0.1] * 3, "drawdown_52w": [-0.3] * 3,
        "return_6m": [-0.2, -0.2, 0.05],
        "sector_return_6m_median": [-0.18, -0.10, -0.05],
        "topix_return_6m": [-0.1, -0.1, np.nan],
        "topix_relative_return_6m": [-0.1, -0.05, np.nan],
        "topix_available": [True, True, False],
        "benchmark_source": ["official_topix", "official_topix", "none"],
        "forecast_op_growth": [0.1] * 3, "quantitative_score": [80.0] * 3,
        "cash_conversion_ratio": [1.0] * 3, "operating_margin_change_3y": [0.0] * 3,
        "forecast_revision_rate": [0.0] * 3, "sector_relative_return_6m": [0.0] * 3,
        "forecast_dividend_yield": [0.0] * 3, "forecast_annual_dividend_per_share": [0.0] * 3,
        "payout_ratio": [0.0] * 3, "forecast_dividend_change_rate": [0.0] * 3,
    })


def test_zero_external_attribution_threshold_preserves_pre_b_candidates():
    prepared = _prepared_attribution_rows()
    config = _config()
    config["screen"].update({
        "minimum_equity_ratio": 0.0,
        "minimum_operating_cf_positive_ratio_3y": 0.0,
        "minimum_sales_cagr_3y": -1.0,
        "minimum_operating_margin": -1.0,
        "minimum_drawdown_52w": 0.0,
        "use_relative_underperformance_filter": False,
        "minimum_sector_relative_return_6m": -1.0,
    })
    before = apply_quantitative_criteria(prepared, config)
    explicit_zero = deepcopy(config)
    explicit_zero["screen"]["minimum_external_shock_attribution"] = 0.0
    after = apply_quantitative_criteria(prepared, explicit_zero)
    assert before.loc[before["selected_for_review"], "code"].tolist() == after.loc[after["selected_for_review"], "code"].tolist()


def test_external_attribution_below_threshold_is_filtered():
    prepared = _prepared_attribution_rows()
    config = _config()
    config["screen"].update({
        "minimum_equity_ratio": 0.0,
        "minimum_operating_cf_positive_ratio_3y": 0.0,
        "minimum_sales_cagr_3y": -1.0,
        "minimum_operating_margin": -1.0,
        "minimum_drawdown_52w": 0.0,
        "use_relative_underperformance_filter": False,
        "minimum_sector_relative_return_6m": -1.0,
        "minimum_external_shock_attribution": 0.7,
    })
    evaluated = apply_quantitative_criteria(prepared, config).set_index("code")
    assert evaluated.loc["A", "external_shock_attribution"] >= 0.7
    assert evaluated.loc["B", "external_shock_attribution"] < 0.7
    assert bool(evaluated.loc["A", "selected_for_review"])
    assert not bool(evaluated.loc["B", "selected_for_review"])


def test_missing_attribution_policy_skip_warns_or_fails():
    prepared = _prepared_attribution_rows()
    common = {
        "minimum_equity_ratio": 0.0,
        "minimum_operating_cf_positive_ratio_3y": 0.0,
        "minimum_sales_cagr_3y": -1.0,
        "minimum_operating_margin": -1.0,
        "minimum_drawdown_52w": 0.0,
        "use_relative_underperformance_filter": False,
        "minimum_sector_relative_return_6m": -1.0,
        "minimum_external_shock_attribution": 0.5,
    }
    skip_config = _config()
    skip_config["screen"].update(common | {"external_shock_attribution_when_missing": "skip_with_warning"})
    fail_config = _config()
    fail_config["screen"].update(common | {"external_shock_attribution_when_missing": "fail"})
    skip = apply_quantitative_criteria(prepared, skip_config).set_index("code")
    fail = apply_quantitative_criteria(prepared, fail_config).set_index("code")
    assert bool(skip.loc["C", "pass_external_shock_attribution"])
    assert bool(skip.loc["C", "external_shock_attribution_skipped"])
    assert "計算できない" in skip.loc["C", "warning_reasons"]
    assert not bool(fail.loc["C", "pass_external_shock_attribution"])
    assert not bool(fail.loc["C", "selected_for_review"])
    skip_funnel = {row["stage"]: row["count"] for row in screening_funnel(skip.reset_index())}
    fail_funnel = {row["stage"]: row["count"] for row in screening_funnel(fail.reset_index())}
    assert skip_funnel["計算できずに通した件数"] == 1
    assert fail_funnel["外因説明率で外れた件数"] == 1


def test_screen_comparison_reuses_prepared_rows_without_fetching(monkeypatch):
    import value_dislocation.strategy.criteria as criteria

    def forbidden(*args, **kwargs):
        raise AssertionError("comparison must not rebuild or fetch data")

    monkeypatch.setattr(criteria, "prepare_quantitative_universe", forbidden)
    assert "create_client" not in criteria.__dict__
    assert "fetch_yahoo_finance_history" not in criteria.__dict__
    assert "fetch_yahoo_finance_quote" not in criteria.__dict__
    comparison = external_attribution_screen_comparison(_prepared_attribution_rows(), _config())
    assert len(comparison) == 8
    no_attribution = comparison.loc[comparison["外因説明率下限"].eq("なし")].set_index("TOPIX比 -8%以下")
    assert no_attribution.loc["なし", "定量候補数"] > no_attribution.loc["あり", "定量候補数"]


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


def test_legacy_42_and_new_70_thresholds_select_same_securities():
    from value_dislocation.strategy.criteria import apply_quantitative_criteria

    prepared = pd.DataFrame({
        "code": ["A", "B", "C"], "market": ["Prime"] * 3,
        "average_turnover_yen_20d": [10_000_000] * 3, "close": [1000] * 3,
        "equity_ratio": [0.5] * 3, "operating_profit_latest": [100] * 3,
        "operating_cf_positive_ratio_3y": [1.0] * 3, "sales_cagr_3y": [0.05] * 3,
        "operating_margin": [0.1] * 3, "drawdown_52w": [-0.3] * 3,
        "relative_return_6m": [-0.2] * 3, "forecast_op_growth": [0.1] * 3,
        "forecast_dividend_yield": [0.0] * 3, "forecast_annual_dividend_per_share": [0.0] * 3,
        "payout_ratio": [0.0] * 3, "forecast_dividend_change_rate": [0.0] * 3,
        "cash_conversion_ratio": [1.0] * 3, "operating_margin_change_3y": [0.0] * 3,
        "forecast_revision_rate": [0.0] * 3, "sector_relative_return_6m": [0.0] * 3,
        "quantitative_score": [69.0, 70.0, 85.0], "daytrade_activity_score": [0.0] * 3,
    })
    base = _config()
    base["screen"].update({"minimum_equity_ratio": 0, "minimum_operating_cf_positive_ratio_3y": 0,
                           "minimum_sales_cagr_3y": -1, "minimum_operating_margin": -1,
                           "minimum_drawdown_52w": 0, "minimum_relative_underperformance_6m": 0,
                           "minimum_sector_relative_return_6m": -1, "quantitative_min_score": 70})
    new = apply_quantitative_criteria(prepared, base)
    legacy_representation = prepared.copy()
    legacy_representation["quantitative_score"] -= 28
    legacy = deepcopy(base)
    legacy["screen"]["quantitative_min_score"] = 42
    old = apply_quantitative_criteria(legacy_representation, legacy)
    assert new.loc[new["selected_for_review"], "code"].tolist() == old.loc[old["selected_for_review"], "code"].tolist()
