from __future__ import annotations

import numpy as np
import pandas as pd

from value_dislocation.decision.buy_readiness import build_buy_readiness
from value_dislocation.strategy.criteria import apply_quantitative_criteria, prepare_quantitative_universe
from value_dislocation.strategy.features import financial_features


def _financial_rows() -> pd.DataFrame:
    rows = []
    for year, sales, op, cfo, forecast, kind, disclosed in [
        (2022, 1_000.0, 100.0, 90.0, np.nan, "FY", "2023-05-10"),
        (2023, 1_050.0, 94.5, 90.0, np.nan, "FY", "2024-05-10"),
        # FY2024 forecast is for FY2025.
        (2024, 1_100.0, 88.0, 70.4, 120.0, "FY", "2025-05-10"),
        # Q1 FY2025 forecasts the same FY2025 and revises it downward.
        (2025, 300.0, 15.0, np.nan, 90.0, "1Q", "2025-08-10"),
    ]:
        rows.append({
            "code": "11110", "disclosure_date": pd.Timestamp(disclosed),
            "statement_type": kind, "period_end": pd.Timestamp(f"{year}-03-31"),
            "fiscal_year": year, "is_full_year_actual": kind == "FY",
            "sales": sales, "operating_profit": op, "operating_cf": cfo,
            "total_assets": 2_000.0, "equity": 1_000.0, "cash": 300.0,
            "interest_bearing_debt": np.nan, "eps": 100.0,
            "book_value_per_share": 500.0, "forecast_operating_profit": forecast,
        })
    return pd.DataFrame(rows)


def test_financial_features_measure_cash_quality_margin_deterioration_and_revision():
    f = financial_features(_financial_rows(), pd.Timestamp("2025-09-01"))
    row = f.iloc[0]
    assert row["cash_conversion_ratio"] == pytest.approx(0.8)
    assert row["operating_margin_change_3y"] == pytest.approx(-0.02)
    assert row["forecast_revision_rate"] == pytest.approx(-0.25)
    assert row["forecast_revision_target_year"] == pytest.approx(2025)


def _companies() -> pd.DataFrame:
    return pd.DataFrame({
        "code": [f"{i:04d}0" for i in range(1, 7)],
        "name": [f"C{i}" for i in range(1, 7)],
        "sector": ["TestSector"] * 6,
        "market": ["Prime"] * 6,
        "shares_outstanding": [1_000_000] * 6,
    })


def _prices() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=150)
    frames = []
    # First stock is much weaker than its peers.
    endings = [70.0, 100.0, 102.0, 104.0, 106.0, 108.0]
    for code, ending in zip(_companies()["code"], endings):
        close = np.linspace(100.0, ending, len(dates))
        frames.append(pd.DataFrame({
            "date": dates, "code": code, "open": close, "high": close * 1.01,
            "low": close * 0.99, "close": close, "volume": 100_000,
            "turnover_yen": close * 100_000,
        }))
    return pd.concat(frames, ignore_index=True)


def _financials_for_universe() -> pd.DataFrame:
    base = _financial_rows()
    frames = []
    for code in _companies()["code"]:
        copy = base.copy()
        copy["code"] = code
        # Avoid forecast-revision failure here; this test targets sector context.
        copy.loc[copy["statement_type"].eq("1Q"), "forecast_operating_profit"] = 120.0
        frames.append(copy)
    return pd.concat(frames, ignore_index=True)


def _config() -> dict:
    return {
        "universe": {"allowed_markets": ["Prime"], "min_average_turnover_yen_20d": 0, "min_price_yen": 0},
        "screen": {
            "minimum_equity_ratio": 0.0, "minimum_operating_cf_positive_ratio_3y": 0.0,
            "minimum_sales_cagr_3y": -1.0, "minimum_operating_margin": -1.0,
            "maximum_forecast_op_decline": -1.0, "require_forecast": False,
            "minimum_drawdown_52w": 0.0, "minimum_relative_underperformance_6m": -1.0,
            "use_relative_underperformance_filter": False, "market_benchmark_mode": "disabled",
            "relative_filter_when_topix_missing": "skip_with_warning", "quantitative_min_score": 0,
            "use_structural_deterioration_guard": True,
            "minimum_cash_conversion_ratio": 0.70,
            "minimum_operating_margin_change_3y": -0.03,
            "minimum_forecast_revision_rate": -0.10,
            "minimum_sector_relative_return_6m": -0.15,
            "require_dividend": False,
        },
    }


def test_sector_relative_weakness_blocks_company_specific_laggard():
    prepared = prepare_quantitative_universe(
        _companies(), _prices(), _financials_for_universe(), _prices()["date"].max()
    )
    weak = prepared.loc[prepared["code"].eq("00010")].iloc[0]
    assert weak["sector_peer_count_6m"] == 6
    assert weak["sector_relative_return_6m"] < -0.15
    evaluated = apply_quantitative_criteria(prepared, _config())
    weak_evaluated = evaluated.loc[evaluated["code"].eq("00010")].iloc[0]
    assert not bool(weak_evaluated["pass_structural_deterioration_guard"])
    assert "同業他社対比" in weak_evaluated["structural_guard_failures"]
    assert not bool(weak_evaluated["selected_for_review"])


def test_missing_structural_metric_warns_without_fabricating_failure():
    prepared = prepare_quantitative_universe(
        _companies(), _prices(), _financials_for_universe(), _prices()["date"].max()
    ).drop(columns=["forecast_revision_rate"])
    cfg = _config()
    cfg["screen"]["minimum_sector_relative_return_6m"] = -1.0
    evaluated = apply_quantitative_criteria(prepared, cfg)
    row = evaluated.iloc[0]
    assert bool(row["pass_forecast_revision"])
    assert "比較可能な会社予想修正履歴なし" in row["warning_reasons"]


def test_known_bad_cash_quality_is_a_buy_readiness_blocker():
    readiness = build_buy_readiness({
        "drawdown_52w": -0.25, "relative_return_6m": -0.10,
        "sales_cagr_3y": 0.03, "operating_margin": 0.08, "equity_ratio": 0.50,
        "operating_cf_positive_ratio_3y": 1.0, "cash_conversion_ratio": 0.20,
        "operating_margin_change_3y": 0.0, "forecast_revision_rate": 0.0,
        "sector_relative_return_6m": 0.0, "forecast_op_growth": 0.05,
    }, external_quote_available=True)
    checks = {item["key"]: item for item in readiness["checks"]}
    assert checks["cash_quality"]["status"] == "fail"
    assert readiness["decision_level"] == "stop"


# pytest is imported late to keep the fixture data visually compact above.
import pytest
