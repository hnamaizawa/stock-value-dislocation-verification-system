from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from value_dislocation.strategy.criteria import apply_quantitative_criteria
from value_dislocation.strategy.features import financial_features


def _config() -> dict:
    return yaml.safe_load(Path("config/real_data.yaml").read_text(encoding="utf-8"))


def _prepared_row(**overrides) -> pd.DataFrame:
    row = {
        "code": "9999",
        "sector": "電気機器",
        "market": "Prime",
        "average_turnover_yen_20d": 100_000_000.0,
        "close": 1000.0,
        "equity_ratio": 0.50,
        "operating_profit_latest": 12_000.0,
        "operating_cf_positive_ratio_3y": 1.0,
        "sales_cagr_3y": 0.04,
        "operating_margin": 0.10,
        "drawdown_52w": -0.25,
        "topix_available": True,
        "topix_proxy_available": False,
        "topix_relative_return_6m": -0.12,
        "topix_proxy_relative_return_6m": np.nan,
        "forecast_op_growth": 0.05,
        "dividend_data_available": False,
        "forecast_dividend_yield": np.nan,
        "forecast_annual_dividend_per_share": np.nan,
        "payout_ratio": np.nan,
        "forecast_dividend_change_rate": np.nan,
        "volatility_60d": 0.25,
        "average_intraday_range_20d": 0.02,
        "quantitative_score": 70.0,
        "cash_conversion_ratio_3y": 0.95,
        "operating_profit_cagr_3y": 0.08,
        "forecast_revision_rate": 0.05,
        "net_cash_to_assets": 0.10,
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_financial_features_add_recovery_quality_inputs():
    financials = pd.DataFrame(
        [
            {"code": "9999", "disclosure_date": "2024-05-01", "fiscal_year": 2023, "period_end": "2024-03-31", "is_full_year_actual": True, "sales": 100.0, "operating_profit": 10.0, "operating_cf": 8.0, "total_assets": 200.0, "equity": 110.0, "cash": 30.0, "interest_bearing_debt": 25.0, "eps": 50.0, "book_value_per_share": 500.0, "forecast_operating_profit": 11.0, "is_revision": False},
            {"code": "9999", "disclosure_date": "2025-05-01", "fiscal_year": 2024, "period_end": "2025-03-31", "is_full_year_actual": True, "sales": 105.0, "operating_profit": 11.0, "operating_cf": 10.0, "total_assets": 205.0, "equity": 115.0, "cash": 35.0, "interest_bearing_debt": 24.0, "eps": 55.0, "book_value_per_share": 520.0, "forecast_operating_profit": 12.0, "is_revision": False},
            {"code": "9999", "disclosure_date": "2026-05-01", "fiscal_year": 2025, "period_end": "2026-03-31", "is_full_year_actual": True, "sales": 110.0, "operating_profit": 12.0, "operating_cf": 13.0, "total_assets": 210.0, "equity": 120.0, "cash": 40.0, "interest_bearing_debt": 20.0, "eps": 60.0, "book_value_per_share": 540.0, "forecast_operating_profit": 13.0, "is_revision": True},
        ]
    )
    financials["disclosure_date"] = pd.to_datetime(financials["disclosure_date"])
    result = financial_features(financials, pd.Timestamp("2026-09-21")).iloc[0]
    assert result["cash_conversion_ratio_3y"] == pytest_approx(31.0 / 33.0)
    assert result["operating_profit_cagr_3y"] > 0
    assert result["net_cash_to_assets"] == pytest_approx(20.0 / 210.0)
    assert result["forecast_revision_rate"] == pytest_approx(13.0 / 12.0 - 1.0)


def pytest_approx(value: float):
    import pytest
    return pytest.approx(value, rel=1e-6)


def test_recovery_quality_passes_healthy_company_and_rejects_structural_deterioration():
    cfg = _config()
    healthy = apply_quantitative_criteria(_prepared_row(), cfg).iloc[0]
    assert healthy["recovery_quality_observed_components"] == 4
    assert healthy["recovery_quality_score"] >= cfg["screen"]["minimum_recovery_quality_score"]
    assert bool(healthy["pass_recovery_quality"])

    weak = apply_quantitative_criteria(
        _prepared_row(
            cash_conversion_ratio_3y=0.10,
            operating_profit_cagr_3y=-0.30,
            forecast_revision_rate=-0.25,
            net_cash_to_assets=-0.40,
        ),
        cfg,
    ).iloc[0]
    assert weak["recovery_quality_score"] < cfg["screen"]["minimum_recovery_quality_score"]
    assert not bool(weak["pass_recovery_quality"])
    assert not bool(weak["hard_filter_pass"])


def test_recovery_quality_is_missing_safe_when_history_is_insufficient():
    cfg = _config()
    result = apply_quantitative_criteria(
        _prepared_row(
            cash_conversion_ratio_3y=np.nan,
            operating_profit_cagr_3y=np.nan,
            forecast_revision_rate=np.nan,
            net_cash_to_assets=np.nan,
        ),
        cfg,
    ).iloc[0]
    assert result["recovery_quality_observed_components"] == 0
    assert pd.isna(result["recovery_quality_score"])
    assert bool(result["pass_recovery_quality"])


def test_financial_sector_does_not_use_cash_conversion_component():
    cfg = _config()
    result = apply_quantitative_criteria(
        _prepared_row(
            sector="銀行業",
            cash_conversion_ratio_3y=-2.0,
            operating_profit_cagr_3y=0.08,
            forecast_revision_rate=0.05,
            net_cash_to_assets=0.10,
        ),
        cfg,
    ).iloc[0]
    assert result["recovery_quality_observed_components"] == 3
    assert bool(result["pass_recovery_quality"])
