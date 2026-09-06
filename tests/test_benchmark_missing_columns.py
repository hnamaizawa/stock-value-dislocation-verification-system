from pathlib import Path

import pandas as pd
import yaml

from value_dislocation.strategy.criteria import apply_quantitative_criteria


def _config() -> dict:
    root = Path(__file__).resolve().parents[1]
    return yaml.safe_load((root / "config" / "default.yaml").read_text(encoding="utf-8"))


def _prepared() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "code": "12340",
            "name": "Missing Benchmark Test",
            "market": "Prime",
            "average_turnover_yen_20d": 200_000_000,
            "close": 1000.0,
            "equity_ratio": 0.50,
            "operating_profit_latest": 100.0,
            "operating_cf_positive_ratio_3y": 1.0,
            "sales_cagr_3y": 0.02,
            "operating_margin": 0.10,
            "drawdown_52w": -0.30,
            "forecast_op_growth": 0.05,
            "quantitative_score": 70.0,
            "topix_available": False,
            "topix_proxy_available": True,
            "topix_proxy_relative_return_6m": -0.12,
            "topix_proxy_label": "1306",
        }
    ])


def test_auto_mode_works_when_official_topix_value_column_is_absent():
    config = _config()
    config["screen"]["market_benchmark_mode"] = "auto"
    result = apply_quantitative_criteria(_prepared(), config)
    assert result.iloc[0]["relative_return_6m"] == -0.12
    assert result.iloc[0]["benchmark_source"] == "topix_etf_proxy"


def test_official_mode_returns_nan_series_when_official_column_is_absent():
    config = _config()
    config["screen"]["market_benchmark_mode"] = "official_topix"
    result = apply_quantitative_criteria(_prepared(), config)
    assert pd.isna(result.iloc[0]["relative_return_6m"])
    assert not bool(result.iloc[0]["benchmark_available"])
