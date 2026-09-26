from pathlib import Path

import pandas as pd
import pytest

from value_dislocation.history_visuals import (
    condition_outcome_bubbles,
    condition_return_heatmap,
    security_return_bubbles,
)


def _condition_perf() -> pd.DataFrame:
    return pd.DataFrame({
        "条件": ["割安", "高品質"],
        "30日平均": [0.05, -0.02],
        "30日プラス率": [0.75, 0.40],
        "30日確定件数": [8, 5],
        "90日平均": [0.12, 0.03],
        "90日プラス率": [0.80, 0.60],
        "90日確定件数": [5, 3],
    })


def test_condition_heatmap_aligns_return_percent_and_confirmed_counts():
    returns, counts = condition_return_heatmap(_condition_perf())
    assert returns.loc["割安", "30日"] == 5.0
    assert returns.loc["高品質", "90日"] == 3.0
    assert counts.loc["割安", "30日"] == 8
    assert pd.isna(returns.loc["割安", "10日"])


def test_condition_bubbles_expose_three_analysis_dimensions():
    bubbles = condition_outcome_bubbles(_condition_perf(), 30)
    cheap = bubbles.loc[bubbles["条件"] == "割安"].iloc[0]
    assert cheap["平均リターン(%)"] == 5.0
    assert cheap["プラス率(%)"] == 75.0
    assert cheap["確定件数"] == 8


def test_security_bubbles_compare_two_horizons_and_size_by_star_count():
    events = pd.DataFrame({
        "code": ["11110", "11110", "22220"],
        "name": ["A", "A", "B"],
        "return_30d": [0.10, -0.02, 0.05],
        "return_90d": [0.20, 0.10, None],
    })
    bubbles = security_return_bubbles(events, 30, 90)
    assert list(bubbles["code"]) == ["11110"]
    row = bubbles.iloc[0]
    assert row["横軸リターン(%)"] == 4.0
    assert row["縦軸リターン(%)"] == pytest.approx(15.0)
    assert row["◎☆回数"] == 2
    assert row["比較可能件数"] == 2


def test_dashboard_uses_local_analytical_visuals_without_fetch_dependency():
    dashboard = Path("dashboard.py").read_text(encoding="utf-8")
    module = Path("src/value_dislocation/history_visuals.py").read_text(encoding="utf-8")
    assert "条件×期間ヒートマップ" in dashboard
    assert "条件の成績バブル" in dashboard
    assert "銘柄の期間比較バブル" in dashboard
    assert "_render_history_analytical_visuals(star_events, perf)" in dashboard
    assert "go.Heatmap" in dashboard
    assert dashboard.count("go.Scatter") >= 2
    assert "fetch_" not in module
    assert "yfinance" not in module.lower()
    assert "jquants" not in module.lower()
