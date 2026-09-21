from __future__ import annotations

import numpy as np
import pandas as pd

from value_dislocation.strategy.attribution import add_external_shock_attribution
from value_dislocation.strategy_validation import (
    _future_return,
    match_similar_nonselected_peers,
    reversal_confirmation_snapshot,
    run_walk_forward_validation,
    summarize_walk_forward,
)


def test_external_shock_attribution_decomposes_market_sector_and_company():
    frame = pd.DataFrame([
        {
            "return_6m": -0.25,
            "sector_return_6m_median": -0.19,
            "sector_peer_count_6m": 12,
            "topix_available": True,
            "topix_return_6m": -0.07,
            "topix_proxy_available": True,
            "topix_proxy_return_6m": -0.06,
        }
    ])
    row = add_external_shock_attribution(frame).iloc[0]
    assert np.isclose(row["attribution_market_return_6m"], -0.07)
    assert np.isclose(row["attribution_sector_component_6m"], -0.12)
    assert np.isclose(row["attribution_company_component_6m"], -0.06)
    assert np.isclose(row["external_shock_attribution_score"], 76.0)


def test_external_shock_attribution_requires_enough_sector_peers():
    frame = pd.DataFrame([
        {
            "return_6m": -0.25,
            "sector_return_6m_median": -0.19,
            "sector_peer_count_6m": 4,
            "topix_available": True,
            "topix_return_6m": -0.07,
        }
    ])
    row = add_external_shock_attribution(frame).iloc[0]
    assert pd.isna(row["external_shock_attribution_score"])
    assert pd.isna(row["attribution_company_component_6m"])


def _peer_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"code": "A", "sector": "電機", "market": "Prime", "selected_for_review": True, "pass_market": True, "pass_liquidity": True, "pass_price": True, "market_cap": 1000, "drawdown_52w": -0.25, "return_6m": -0.18, "per_vs_sector": 0.9, "pbr_vs_sector": 0.8, "equity_ratio": 0.5},
            {"code": "B", "sector": "電機", "market": "Prime", "selected_for_review": False, "pass_market": True, "pass_liquidity": True, "pass_price": True, "market_cap": 1100, "drawdown_52w": -0.23, "return_6m": -0.16, "per_vs_sector": 0.92, "pbr_vs_sector": 0.82, "equity_ratio": 0.52},
            {"code": "C", "sector": "電機", "market": "Prime", "selected_for_review": False, "pass_market": True, "pass_liquidity": True, "pass_price": True, "market_cap": 950, "drawdown_52w": -0.27, "return_6m": -0.20, "per_vs_sector": 0.88, "pbr_vs_sector": 0.78, "equity_ratio": 0.48},
            {"code": "D", "sector": "電機", "market": "Prime", "selected_for_review": False, "pass_market": True, "pass_liquidity": True, "pass_price": True, "market_cap": 1050, "drawdown_52w": -0.24, "return_6m": -0.17, "per_vs_sector": 0.91, "pbr_vs_sector": 0.81, "equity_ratio": 0.51},
            {"code": "X", "sector": "銀行", "market": "Prime", "selected_for_review": False, "pass_market": True, "pass_liquidity": True, "pass_price": True, "market_cap": 1005, "drawdown_52w": -0.25, "return_6m": -0.18, "per_vs_sector": 0.9, "pbr_vs_sector": 0.8, "equity_ratio": 0.5},
        ]
    )


def test_peer_matching_prefers_same_sector_nonselected_controls():
    peers = match_similar_nonselected_peers(_peer_table(), "A", peer_count=3)
    assert list(peers["code"]) == ["B", "D", "C"] or set(peers["code"]) == {"B", "C", "D"}
    assert set(peers["sector"]) == {"電機"}
    assert "A" not in set(peers["code"])


def test_reversal_confirmation_matches_v061_conditions():
    dates = pd.bdate_range("2025-01-01", periods=80)
    prices = pd.DataFrame({"date": dates, "close": np.linspace(100.0, 180.0, len(dates)), "volume": 1000})
    result = reversal_confirmation_snapshot(prices)
    assert result["trend_score"] >= 5
    assert result["return_20d"] > 0
    assert result["latest_price"] > result["sma20"] > result["sma50"]
    assert result["sma20_rising"] is True
    assert result["reversal_confirmed"] is True


def test_future_return_uses_first_observation_on_or_after_calendar_horizon():
    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02", "2026-01-09", "2026-01-13", "2026-01-14"]),
            "close": [100.0, 105.0, 110.0, 120.0],
        }
    )
    value, actual_days = _future_return(prices, pd.Timestamp("2026-01-02"), 10)
    assert np.isclose(value, 0.10)
    assert actual_days == 11


def test_walk_forward_produces_matched_control_excess(monkeypatch):
    dates = pd.bdate_range("2025-01-01", periods=100)
    candidate_prices = pd.DataFrame({"code": "A", "date": dates, "close": np.linspace(100.0, 200.0, len(dates)), "volume": 1000})
    peer_prices = pd.DataFrame({"code": "B", "date": dates, "close": np.linspace(100.0, 140.0, len(dates)), "volume": 1000})
    prices = pd.concat([candidate_prices, peer_prices], ignore_index=True)

    table = pd.DataFrame(
        [
            {"code": "A", "name": "Candidate", "sector": "電機", "market": "Prime", "selected_for_review": True, "pass_market": True, "pass_liquidity": True, "pass_price": True, "quantitative_score": 80.0, "market_cap": 1000.0, "drawdown_52w": -0.2, "return_6m": -0.1, "per_vs_sector": 0.9, "pbr_vs_sector": 0.9, "equity_ratio": 0.5, "external_shock_attribution_score": 70.0},
            {"code": "B", "name": "Peer", "sector": "電機", "market": "Prime", "selected_for_review": False, "pass_market": True, "pass_liquidity": True, "pass_price": True, "quantitative_score": 50.0, "market_cap": 1100.0, "drawdown_52w": -0.18, "return_6m": -0.08, "per_vs_sector": 0.95, "pbr_vs_sector": 0.95, "equity_ratio": 0.48, "external_shock_attribution_score": 65.0},
        ]
    )

    monkeypatch.setattr("value_dislocation.strategy_validation.prepare_quantitative_universe", lambda *args, **kwargs: table.copy())
    monkeypatch.setattr("value_dislocation.strategy_validation.apply_quantitative_criteria", lambda prepared, config: prepared.copy())

    result = run_walk_forward_validation(
        pd.DataFrame({"code": ["A", "B"]}),
        prices,
        pd.DataFrame(),
        {"screen": {}},
        step_trading_days=20,
        max_evaluation_dates=2,
        event_gap_days=0,
        peer_count=1,
        minimum_history_observations=60,
        horizons=(10,),
    )
    events = result["events"]
    assert not events.empty
    mature = events.dropna(subset=["return_10d", "peer_return_10d_avg", "excess_return_10d"])
    assert not mature.empty
    assert (mature["excess_return_10d"] > 0).all()
    summary = summarize_walk_forward(events, (10,))
    assert int(summary.iloc[0]["対照比較件数"]) >= 1
    assert float(summary.iloc[0]["選択超過平均"]) > 0
