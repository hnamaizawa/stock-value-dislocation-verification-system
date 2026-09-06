from pathlib import Path

import pandas as pd

from value_dislocation.history import (
    daily_evaluation_counts,
    evaluation_symbol_counts,
    star_forward_return_summary,
)


def test_history_chart_aggregations_are_lightweight_and_correct():
    history = pd.DataFrame({
        "analysis_date": ["2026-09-01", "2026-09-01", "2026-09-02"],
        "final_evaluation": ["◎☆", "○", "◎☆"],
    })
    daily = daily_evaluation_counts(history)
    assert daily.loc["2026-09-01", "◎☆"] == 1
    assert daily.loc["2026-09-01", "○"] == 1
    assert daily.loc["2026-09-02", "◎☆"] == 1

    evaluation = pd.DataFrame({"intuitive_symbol": ["◎☆", "◎☆", "○", ""]})
    counts = evaluation_symbol_counts(evaluation)
    assert counts.loc["◎☆", "件数"] == 2
    assert counts.loc["○", "件数"] == 1
    assert counts.loc["未評価", "件数"] == 1

    events = pd.DataFrame({
        "return_30d": [0.10, -0.02, None],
        "return_90d": [0.20, None, None],
        "return_180d": [None, None, None],
    })
    summary = star_forward_return_summary(events)
    assert summary.loc["30日", "確定件数"] == 2
    assert summary.loc["30日", "平均リターン(%)"] == 4.0
    assert summary.loc["30日", "プラス率(%)"] == 50.0
    assert summary.loc["180日", "確定件数"] == 0


def test_history_dashboard_has_visualizations_without_extra_fetch_paths():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert '可視化：当日の最終評価件数の推移' in text
    assert '可視化：最終評価の構成' in text
    assert '可視化：◎☆後の平均リターン' in text
    assert '可視化：条件別{horizon}平均リターン' in text
    assert 'daily_evaluation_counts(hist)' in text
    assert 'evaluation_symbol_counts(e)' in text
    assert 'star_forward_return_summary(star_events)' in text
    assert 'st.line_chart(daily_chart' in text
    assert 'st.bar_chart(symbol_chart' in text
    assert 'st.bar_chart(matured_chart' in text
    assert 'st.bar_chart(condition_chart.set_index("条件")' in text
