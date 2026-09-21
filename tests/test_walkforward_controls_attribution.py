from __future__ import annotations

import numpy as np
import pandas as pd

from value_dislocation.strategy.attribution import add_external_shock_attribution
from value_dislocation.validation import matched_controls, walk_forward_summary


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
