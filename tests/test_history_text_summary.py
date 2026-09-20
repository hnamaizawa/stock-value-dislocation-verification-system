import pandas as pd

from value_dislocation.history import (
    daily_history_text_summary,
    evaluation_history_text_summary,
    star_forward_return_summary,
    star_validation_text_summary,
)


def test_daily_history_text_summary_describes_filtered_result():
    frame = pd.DataFrame([
        {"analysis_date": "2026-09-18", "code": "72030", "final_evaluation": "◎☆", "evaluation_status": "当日評価済み", "unassessed_reason": ""},
        {"analysis_date": "2026-09-19", "code": "94320", "final_evaluation": "◎☆", "evaluation_status": "当日評価済み", "unassessed_reason": ""},
        {"analysis_date": "2026-09-20", "code": "99840", "final_evaluation": "未評価", "evaluation_status": "未評価", "unassessed_reason": "旧履歴"},
    ])
    lines = daily_history_text_summary(frame)
    assert 2 <= len(lines) <= 4
    assert any("3 件" in line or "3件" in line for line in lines)
    assert any("◎☆" in line for line in lines)
    assert any("旧履歴" in line for line in lines)


def test_evaluation_history_text_summary_describes_distribution():
    frame = pd.DataFrame([
        {"evaluation_date": "2026-09-19", "code": "72030", "intuitive_symbol": "◎", "evaluation_status": "当日評価済み"},
        {"evaluation_date": "2026-09-20", "code": "94320", "intuitive_symbol": "○", "evaluation_status": "後日補完"},
        {"evaluation_date": "2026-09-20", "code": "99840", "intuitive_symbol": "×", "evaluation_status": "当日評価済み"},
    ])
    lines = evaluation_history_text_summary(frame)
    assert any("3 件" in line or "3件" in line for line in lines)
    assert any("◎☆/◎" in line for line in lines)
    assert any("後日補完" in line for line in lines)


def test_star_validation_text_summary_uses_matured_returns_and_conditions():
    events = pd.DataFrame([
        {"code": "72030", "return_10d": 0.05, "return_20d": 0.03, "return_30d": 0.02},
        {"code": "94320", "return_10d": 0.01, "return_20d": -0.01, "return_30d": 0.04},
    ])
    forward = star_forward_return_summary(events)
    perf = pd.DataFrame([
        {"条件": "売上CAGR 3%以上", "90日平均": 0.12, "90日確定件数": 8},
        {"条件": "自己資本比率 40%以上", "90日平均": 0.06, "90日確定件数": 10},
    ])
    lines = star_validation_text_summary(events, forward, perf)
    assert any("◎☆開始イベント" in line for line in lines)
    assert any("平均リターン" in line for line in lines)
    assert any("売上CAGR 3%以上" in line for line in lines)


def test_dashboard_renders_summary_on_all_three_history_views():
    text = open("dashboard.py", encoding="utf-8").read()
    assert "_render_history_analysis_summary(daily_history_text_summary(hist))" in text
    assert "_render_history_analysis_summary(evaluation_history_text_summary(e))" in text
    assert "_render_history_analysis_summary(star_validation_text_summary(star_events, forward_chart, perf))" in text
