from __future__ import annotations

from pathlib import Path

import pandas as pd

from value_dislocation.strategy_validation import (
    add_external_shock_attribution,
    matched_peer_event_comparison,
    matched_peer_summary,
    walk_forward_events,
    walk_forward_summary,
)


def test_external_shock_attribution_decomposes_market_sector_and_company():
    frame = pd.DataFrame([{
        "code": "1000",
        "return_6m": -0.20,
        "relative_return_6m": -0.10,
        "sector_relative_return_6m": -0.05,
    }])
    out = add_external_shock_attribution(frame).iloc[0]
    assert round(float(out["benchmark_return_6m_est"]), 6) == -0.10
    assert round(float(out["sector_return_6m_est"]), 6) == -0.15
    assert round(float(out["external_shock_attribution_ratio"]), 6) == 0.75
    assert round(float(out["company_specific_component_6m"]), 6) == -0.05
    assert out["external_shock_attribution_label"] == "外因説明が強い"


def _analysis_rows():
    dates = ["2026-01-01", "2026-01-11", "2026-01-21", "2026-01-31", "2026-03-02", "2026-04-01"]
    rows = []
    prices = {
        "1000": [100, 105, 110, 112, 120, 130],
        "2000": [100, 101, 102, 103, 104, 105],
        "3000": [100, 99, 98, 97, 96, 95],
    }
    for code, values in prices.items():
        for idx, day in enumerate(dates):
            rows.append({
                "analysis_date": day,
                "data_as_of": day,
                "code": code,
                "name": code,
                "market": "Prime",
                "sector": "TEST",
                "selection_strategy": "value_dislocation",
                "selected_for_review": code == "1000",
                "close": values[idx],
                "drawdown_52w": -0.25 if code == "1000" else (-0.24 if code == "2000" else -0.28),
                "relative_return_6m": -0.12 if code == "1000" else (-0.11 if code == "2000" else -0.15),
                "operating_margin": 0.12,
                "equity_ratio": 0.50,
                "return_6m": -0.20,
                "sector_relative_return_6m": -0.05,
            })
    return pd.DataFrame(rows)


def _evaluations():
    return pd.DataFrame([
        {
            "evaluation_date": "2026-01-01",
            "code": "1000",
            "selection_strategy": "value_dislocation",
            "intuitive_symbol": "◎☆",
            "latest_price": 100.0,
            "latest_market_date": "2026-01-01",
            "latest_trend": "上昇トレンド",
            "evaluation_status": "当日評価済み",
            "unassessed_reason": "",
        },
        {
            "evaluation_date": "2026-01-11",
            "code": "1000",
            "selection_strategy": "value_dislocation",
            "intuitive_symbol": "◎☆",
            "latest_price": 105.0,
            "latest_market_date": "2026-01-11",
            "latest_trend": "上昇トレンド",
            "evaluation_status": "当日評価済み",
            "unassessed_reason": "",
        },
        {
            "evaluation_date": "2026-01-21",
            "code": "1000",
            "selection_strategy": "value_dislocation",
            "intuitive_symbol": "○",
            "latest_price": 110.0,
            "latest_market_date": "2026-01-21",
            "latest_trend": "上昇トレンド",
            "evaluation_status": "当日評価済み",
            "unassessed_reason": "",
        },
    ])


def test_walk_forward_uses_saved_signal_and_later_saved_prices_only():
    events = walk_forward_events(_analysis_rows(), _evaluations(), signal_symbols=("◎☆",), horizons=(10, 20, 30))
    assert len(events) == 1
    row = events.iloc[0]
    assert row["analysis_date"] == "2026-01-01"
    assert round(float(row["return_10d"]), 6) == 0.05
    assert round(float(row["return_20d"]), 6) == 0.10
    assert round(float(row["return_30d"]), 6) == 0.12
    summary = walk_forward_summary(events, horizons=(10, 20, 30))
    assert summary["確定件数"].tolist() == [1, 1, 1]


def test_matched_peers_prefer_nonselected_same_sector_and_measure_alpha():
    analysis = _analysis_rows()
    events = walk_forward_events(analysis, _evaluations(), signal_symbols=("◎☆",), horizons=(10, 20))
    comparison = matched_peer_event_comparison(analysis, events, peer_count=2, horizons=(10, 20))
    assert len(comparison) == 1
    row = comparison.iloc[0]
    assert set(str(row["peer_codes"]).split(",")) == {"2000", "3000"}
    assert row["peer_pool"].endswith("非選択")
    assert float(row["selection_alpha_10d"]) > 0
    summary = matched_peer_summary(comparison, horizons=(10, 20))
    assert int(summary.iloc[0]["比較可能イベント"]) == 1
    assert float(summary.iloc[0]["選択効果"]) > 0


def test_v063_dashboard_and_version_contract():
    dashboard = Path("dashboard.py").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    blueprint = Path("harness/app_blueprint.yaml").read_text(encoding="utf-8")
    assert '"戦略検証"' in dashboard
    assert "walk_forward_events" in dashboard
    assert "matched_peer_event_comparison" in dashboard
    assert "latest_external_shock_attribution" in dashboard
    assert "Version: **0.6.63**" in readme
    assert "blueprint_version: 0.6.63" in blueprint
