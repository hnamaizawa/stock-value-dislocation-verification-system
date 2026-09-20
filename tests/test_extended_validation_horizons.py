from datetime import timedelta

import pandas as pd

from value_dislocation.history import (
    STAR_OUTCOME_HORIZONS,
    build_star_events,
    condition_performance,
    star_forward_return_summary,
    summarize_star_outcomes_by_code,
)


def test_star_outcome_horizons_include_requested_short_and_mid_terms_in_order():
    assert STAR_OUTCOME_HORIZONS == (10, 20, 30, 60, 90, 180)


def test_build_star_events_computes_all_extended_horizons():
    start = pd.Timestamp("2026-01-01")
    closes = {0: 100.0, 10: 101.0, 20: 102.0, 30: 103.0, 60: 106.0, 90: 109.0, 180: 118.0}
    rows = []
    for days, close in closes.items():
        rows.append({
            "evaluation_date": (start + timedelta(days=days)).date().isoformat(),
            "latest_market_date": (start + timedelta(days=days)).date().isoformat(),
            "code": "72030",
            "name": "テスト",
            "intuitive_symbol": "◎☆" if days == 0 else "○",
            "latest_price": close,
            "latest_trend": "上昇",
        })
    events = build_star_events(pd.DataFrame(rows))
    assert len(events) == 1
    event = events.iloc[0]
    for horizon in STAR_OUTCOME_HORIZONS:
        assert round(float(event[f"return_{horizon}d"]), 6) == round(closes[horizon] / 100.0 - 1.0, 6)
        assert int(event[f"actual_days_{horizon}d"]) == horizon


def test_forward_summary_and_code_summary_expose_all_horizons():
    row = {"code": "72030", "name": "テスト", "star_date": "2026-01-01", "entry_price": 100.0}
    for horizon in STAR_OUTCOME_HORIZONS:
        row[f"return_{horizon}d"] = horizon / 1000.0
    events = pd.DataFrame([row])
    forward = star_forward_return_summary(events)
    assert list(forward.index) == [f"{h}日" for h in STAR_OUTCOME_HORIZONS]
    summary = summarize_star_outcomes_by_code(events)
    for horizon in STAR_OUTCOME_HORIZONS:
        assert f"return_{horizon}d_avg" in summary.columns
        assert f"completed_{horizon}d" in summary.columns
        assert int(summary.iloc[0][f"completed_{horizon}d"]) == 1


def test_dashboard_uses_extended_horizons_for_history_validation():
    text = open("dashboard.py", encoding="utf-8").read()
    assert "Yahooで10/20/30/60/90/180日実績を更新" in text
    assert "for h in STAR_OUTCOME_HORIZONS" in text
    assert '[f"{h}日" for h in STAR_OUTCOME_HORIZONS]' in text
    assert 'for idx, horizon in enumerate((10, 20, 30), start=1)' in text
    assert 'for idx, horizon in enumerate((60, 90, 180))' in text


def test_legacy_star_outcomes_without_new_horizon_columns_are_treated_as_unmatured(tmp_path):
    analysis_dir = tmp_path / "data" / "history" / "analysis"
    analysis_dir.mkdir(parents=True)
    pd.DataFrame([{
        "analysis_date": "2026-01-01",
        "code": "72030",
        "sales_cagr_3y": 0.05,
        "operating_margin": 0.12,
        "equity_ratio": 0.50,
        "drawdown_52w": -0.25,
        "relative_return_6m": -0.12,
        "forecast_op_growth": 0.10,
        "forecast_dividend_yield": 0.04,
        "volatility_60d": 0.40,
        "average_intraday_range_20d": 0.03,
    }]).to_csv(analysis_dir / "2026-01-01.csv.gz", index=False, compression="gzip")

    legacy_events = pd.DataFrame([{
        "code": "72030",
        "name": "テスト",
        "star_date": "2026-01-01",
        "entry_price": 100.0,
        "return_30d": 0.03,
        "return_90d": 0.09,
        "return_180d": 0.18,
    }])
    perf = condition_performance(tmp_path, legacy_events)
    assert not perf.empty
    for horizon in (10, 20, 60):
        assert f"{horizon}日確定件数" in perf.columns
        assert (perf[f"{horizon}日確定件数"] == 0).all()
