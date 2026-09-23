from __future__ import annotations

import numpy as np
import pandas as pd

from value_dislocation.strategy.attribution import add_external_shock_attribution
from value_dislocation import validation
from value_dislocation.validation import (
    WalkForwardConfig,
    _forward_return,
    matched_controls,
    walk_forward_summary,
    walk_forward_validation,
)


def test_external_shock_attribution_decomposes_decline():
    frame = pd.DataFrame([
        {"return_6m": -0.25, "sector_return_6m_median": -0.19, "benchmark_return_6m": -0.07},
    ])
    out = add_external_shock_attribution(frame).iloc[0]
    assert out["market_return_component_6m"] == -0.07
    assert np.isclose(out["sector_incremental_component_6m"], -0.12)
    assert np.isclose(out["company_specific_component_6m"], -0.06)
    assert np.isclose(out["external_shock_attribution"], 0.76)
    assert np.isclose(out["external_shock_attribution_score"], 76.0)


def test_external_shock_attribution_does_not_invent_missing_benchmark():
    frame = pd.DataFrame([
        {"return_6m": -0.20, "sector_return_6m_median": -0.15, "benchmark_return_6m": np.nan},
    ])
    out = add_external_shock_attribution(frame).iloc[0]
    assert pd.isna(out["external_shock_attribution"])
    assert not bool(out["external_shock_attribution_available"])


def test_matched_controls_prefers_same_sector_non_selected():
    universe = pd.DataFrame([
        {"code": "A", "sector": "Tech", "market": "Prime", "selected_for_review": True, "market_cap": 100, "drawdown_52w": -0.2, "volatility_60d": 0.3, "per_vs_sector": 1.0, "pbr_vs_sector": 1.0},
        {"code": "B", "sector": "Tech", "market": "Prime", "selected_for_review": False, "market_cap": 105, "drawdown_52w": -0.21, "volatility_60d": 0.31, "per_vs_sector": 1.02, "pbr_vs_sector": 0.98},
        {"code": "C", "sector": "Tech", "market": "Prime", "selected_for_review": False, "market_cap": 95, "drawdown_52w": -0.19, "volatility_60d": 0.29, "per_vs_sector": 0.98, "pbr_vs_sector": 1.03},
        {"code": "D", "sector": "Tech", "market": "Prime", "selected_for_review": False, "market_cap": 110, "drawdown_52w": -0.22, "volatility_60d": 0.32, "per_vs_sector": 1.03, "pbr_vs_sector": 1.04},
        {"code": "E", "sector": "Retail", "market": "Prime", "selected_for_review": False, "market_cap": 101, "drawdown_52w": -0.20, "volatility_60d": 0.30, "per_vs_sector": 1.0, "pbr_vs_sector": 1.0},
    ])
    controls = matched_controls(universe, universe.iloc[0], count=3)
    assert set(controls["code"]) == {"B", "C", "D"}
    assert not controls["selected_for_review"].any()


def test_walk_forward_summary_reports_selection_edge():
    events = pd.DataFrame([
        {"return_30d": 0.10, "control_return_30d": 0.02, "selection_edge_30d": 0.08},
        {"return_30d": -0.02, "control_return_30d": -0.05, "selection_edge_30d": 0.03},
    ])
    row = walk_forward_summary(events, horizons=(30,)).iloc[0]
    assert row["確定件数"] == 2
    assert np.isclose(row["候補平均"], 0.04)
    assert np.isclose(row["類似非選択平均"], -0.015)
    assert np.isclose(row["選択効果"], 0.055)
    assert np.isclose(row["選択効果プラス率"], 1.0)


def test_matched_controls_backfills_same_market_after_sector_priority():
    universe = pd.DataFrame([
        {"code": "A", "sector": "Tech", "market": "Prime", "selected_for_review": True, "market_cap": 100, "drawdown_52w": -0.2, "volatility_60d": 0.3, "per_vs_sector": 1.0, "pbr_vs_sector": 1.0},
        {"code": "B", "sector": "Tech", "market": "Prime", "selected_for_review": False, "market_cap": 500, "drawdown_52w": -0.4, "volatility_60d": 0.5, "per_vs_sector": 1.5, "pbr_vs_sector": 1.5},
        {"code": "C", "sector": "Retail", "market": "Prime", "selected_for_review": False, "market_cap": 101, "drawdown_52w": -0.2, "volatility_60d": 0.3, "per_vs_sector": 1.0, "pbr_vs_sector": 1.0},
        {"code": "D", "sector": "Bank", "market": "Prime", "selected_for_review": False, "market_cap": 102, "drawdown_52w": -0.2, "volatility_60d": 0.3, "per_vs_sector": 1.0, "pbr_vs_sector": 1.0},
    ])
    controls = matched_controls(universe, universe.iloc[0], count=3)
    assert controls["code"].tolist()[0] == "B"
    assert set(controls["code"]) == {"B", "C", "D"}


def test_forward_return_uses_trading_sessions_not_calendar_days():
    dates = pd.to_datetime(["2026-01-09", "2026-01-12", "2026-01-13", "2026-01-14"])
    groups = {"A": pd.DataFrame({"date": dates, "close": [100.0, 101.0, 110.0, 120.0]})}
    result, actual_days = _forward_return(groups, "A", pd.Timestamp("2026-01-09"), 100.0, 2)
    assert np.isclose(result, 0.10)
    assert actual_days == 4


def test_walk_forward_filters_future_inputs_before_selection(monkeypatch):
    dates = pd.bdate_range("2026-01-05", periods=15)
    prices = pd.DataFrame({
        "code": ["A"] * len(dates),
        "date": dates,
        "close": np.linspace(100.0, 114.0, len(dates)),
    })
    financials = pd.DataFrame([
        {"code": "A", "disclosure_date": dates[0], "marker": "past"},
        {"code": "A", "disclosure_date": dates[-1], "marker": "future"},
    ])
    companies = pd.DataFrame([{"code": "A", "name": "A社", "sector": "Tech", "market": "Prime"}])
    observed = {}

    def fake_prepare(c, p, f, as_of):
        observed["as_of"] = pd.Timestamp(as_of)
        observed["max_price"] = p["date"].max()
        observed["max_disclosure"] = f["disclosure_date"].max()
        return pd.DataFrame([{
            "code": "A", "name": "A社", "sector": "Tech", "market": "Prime",
            "close": float(p.iloc[-1]["close"]), "return_6m": -0.1,
        }])

    def fake_apply(prepared, config):
        out = prepared.copy()
        out["selected_for_review"] = True
        return out

    monkeypatch.setattr(validation, "prepare_quantitative_universe", fake_prepare)
    monkeypatch.setattr(validation, "apply_quantitative_criteria", fake_apply)
    events = walk_forward_validation(
        companies, prices, financials, {},
        settings=WalkForwardConfig(
            max_snapshots=1, spacing_trading_days=1,
            controls_per_event=1, minimum_history_trading_days=1,
        ),
        horizons=(2,),
    )
    assert not events.empty
    assert observed["max_price"] <= observed["as_of"]
    assert observed["max_disclosure"] <= observed["as_of"]
    assert events.iloc[0]["universe_source"].startswith("current_master_fallback")


def test_walk_forward_module_has_no_market_fetch_dependency():
    source = __import__("inspect").getsource(validation)
    assert "fetch_and_curate_jquants" not in source
    assert "yfinance" not in source
