from pathlib import Path
import textwrap


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:160]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


history = Path("src/value_dislocation/history.py")
text = history.read_text(encoding="utf-8")
anchor = 'EVALUATION_SYMBOL_ORDER = ["◎☆", "◎", "○", "△", "×", "未評価", "対象外"]\n'
helpers = textwrap.dedent('''\
def _summary_text_column(frame: pd.DataFrame | None, column: str) -> pd.Series:
    if frame is None:
        return pd.Series(dtype="string")
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype="string")
    values = frame[column]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, -1] if values.shape[1] else pd.Series("", index=frame.index, dtype="string")
    return values.fillna("").astype("string").str.strip()


def _summary_date_span(frame: pd.DataFrame, column: str) -> str:
    if frame is None or frame.empty or column not in frame.columns:
        return "期間不明"
    dates = pd.to_datetime(_summary_text_column(frame, column), errors="coerce").dropna()
    if dates.empty:
        return "期間不明"
    first = dates.min().date().isoformat()
    last = dates.max().date().isoformat()
    return first if first == last else f"{first}〜{last}"


def daily_history_text_summary(history: pd.DataFrame) -> list[str]:
    """Build a short deterministic summary for the filtered daily-history view."""
    if history is None or history.empty:
        return ["現在の条件に該当する日次分析履歴はありません。"]
    frame = history.copy()
    codes = _summary_text_column(frame, "code")
    unique_codes = int(codes.loc[codes.ne("")].nunique())
    lines = [f"表示中は {len(frame):,} 件（{unique_codes:,} 銘柄）、対象期間は {_summary_date_span(frame, 'analysis_date')} です。"]
    symbols = _summary_text_column(frame, "final_evaluation")
    symbol_counts = symbols.loc[symbols.ne("")].value_counts()
    if not symbol_counts.empty:
        top_symbol = str(symbol_counts.index[0])
        top_count = int(symbol_counts.iloc[0])
        lines.append(f"最終評価では「{top_symbol}」が最多で {top_count:,} 件（{top_count / len(frame) * 100:.1f}%）です。")
    positive = int(symbols.isin(["◎☆", "◎", "○"]).sum())
    cautious = int(symbols.isin(["△", "×"]).sum())
    if positive or cautious:
        lines.append(f"◎☆/◎/○ は計 {positive:,} 件、△/× は計 {cautious:,} 件です。")
    statuses = _summary_text_column(frame, "evaluation_status")
    unassessed = int(statuses.eq("未評価").sum())
    if unassessed:
        reasons = _summary_text_column(frame.loc[statuses.eq("未評価")], "unassessed_reason")
        reason_counts = reasons.loc[reasons.ne("")].value_counts()
        reason_text = f" 主因は「{reason_counts.index[0]}」です。" if not reason_counts.empty else ""
        lines.append(f"未評価が {unassessed:,} 件（{unassessed / len(frame) * 100:.1f}%）残っています。{reason_text}".strip())
    return lines[:4]


def evaluation_history_text_summary(evaluations: pd.DataFrame) -> list[str]:
    """Build a short deterministic summary for the filtered final-evaluation history."""
    if evaluations is None or evaluations.empty:
        return ["現在の条件に該当する評価履歴はありません。"]
    frame = evaluations.copy()
    codes = _summary_text_column(frame, "code")
    unique_codes = int(codes.loc[codes.ne("")].nunique())
    lines = [f"表示中は {len(frame):,} 件（{unique_codes:,} 銘柄）、評価日は {_summary_date_span(frame, 'evaluation_date')} です。"]
    symbols = _summary_text_column(frame, "intuitive_symbol")
    counts = symbols.loc[symbols.ne("")].value_counts()
    if not counts.empty:
        top_symbol = str(counts.index[0])
        top_count = int(counts.iloc[0])
        lines.append(f"保存評価では「{top_symbol}」が最多で {top_count:,} 件（{top_count / len(frame) * 100:.1f}%）です。")
    high = int(symbols.isin(["◎☆", "◎"]).sum())
    watch = int(symbols.isin(["○", "△"]).sum())
    avoid = int(symbols.eq("×").sum())
    if high or watch or avoid:
        lines.append(f"◎☆/◎ は {high:,} 件、○/△ は {watch:,} 件、× は {avoid:,} 件です。")
    statuses = _summary_text_column(frame, "evaluation_status")
    backfilled = int(statuses.eq("後日補完").sum())
    if backfilled:
        lines.append(f"後日補完された評価が {backfilled:,} 件あり、当日評価とは区別して保存されています。")
    return lines[:4]


def star_validation_text_summary(
    events: pd.DataFrame,
    forward_summary: pd.DataFrame,
    condition_perf: pd.DataFrame | None = None,
    *,
    condition_horizon: int = 90,
) -> list[str]:
    """Build a compact non-causal summary of ◎☆ forward-return validation."""
    if events is None or events.empty:
        return ["◎☆開始イベントがまだないため、実績サマリを作成できません。"]
    codes = _summary_text_column(events, "code")
    unique_codes = int(codes.loc[codes.ne("")].nunique())
    lines = [f"◎☆開始イベントは {len(events):,} 件、対象は {unique_codes:,} 銘柄です。"]

    forward = pd.DataFrame() if forward_summary is None else forward_summary.reset_index().copy()
    if not forward.empty and {"期間", "平均リターン(%)", "確定件数"}.issubset(forward.columns):
        forward["平均リターン(%)"] = pd.to_numeric(forward["平均リターン(%)"], errors="coerce")
        forward["確定件数"] = pd.to_numeric(forward["確定件数"], errors="coerce").fillna(0)
        matured = forward.loc[(forward["確定件数"] > 0) & forward["平均リターン(%)"].notna()].copy()
        if matured.empty:
            lines.append("10〜180日の将来リターンはまだ十分に確定していません。")
        else:
            best = matured.sort_values("平均リターン(%)", ascending=False).iloc[0]
            lines.append(f"確定済み期間では {best['期間']} の平均リターンが最も高く {float(best['平均リターン(%)']):+.1f}%（{int(best['確定件数']):,}件）です。")
            positive_periods = int((matured["平均リターン(%)"] > 0).sum())
            lines.append(f"平均リターンがプラスの期間は、確定済み {len(matured):,} 期間中 {positive_periods:,} 期間です。")

    perf = pd.DataFrame() if condition_perf is None else condition_perf.copy()
    avg_col = f"{condition_horizon}日平均"
    count_col = f"{condition_horizon}日確定件数"
    if not perf.empty and {"条件", avg_col, count_col}.issubset(perf.columns):
        perf[avg_col] = pd.to_numeric(perf[avg_col], errors="coerce")
        perf[count_col] = pd.to_numeric(perf[count_col], errors="coerce").fillna(0)
        usable = perf.loc[(perf[count_col] > 0) & perf[avg_col].notna()].copy()
        if not usable.empty:
            best_condition = usable.sort_values(avg_col, ascending=False).iloc[0]
            lines.append(f"条件別では「{best_condition['条件']}」の{condition_horizon}日平均が最も高く {float(best_condition[avg_col]) * 100:+.1f}%（{int(best_condition[count_col]):,}件）です。因果関係ではなく参考傾向です。")
    return lines[:4]


''')
if "def daily_history_text_summary(" not in text:
    if anchor not in text:
        raise SystemExit("summary helper anchor not found")
    text = text.replace(anchor, helpers + anchor, 1)
history.write_text(text, encoding="utf-8")


dashboard = Path("dashboard.py")
text = dashboard.read_text(encoding="utf-8")
text = text.replace(
    '    daily_evaluation_counts,\n    evaluation_symbol_counts,\n',
    '    daily_evaluation_counts,\n    daily_history_text_summary,\n    evaluation_history_text_summary,\n    evaluation_symbol_counts,\n',
    1,
)
text = text.replace(
    '    star_forward_return_summary,\n    write_star_outcomes,\n',
    '    star_forward_return_summary,\n    star_validation_text_summary,\n    write_star_outcomes,\n',
    1,
)
anchor = '\n\ndef _render_history_daily(evaluation_signature) -> None:\n'
helper = '\n\ndef _render_history_analysis_summary(lines: list[str], *, title: str = "分析結果サマリ") -> None:\n    if not lines:\n        return\n    with st.container(border=True):\n        st.markdown(f"#### {title}")\n        st.markdown("\\n".join(f"- {line}" for line in lines))\n\n\ndef _render_history_daily(evaluation_signature) -> None:\n'
if "def _render_history_analysis_summary(" not in text:
    if anchor not in text:
        raise SystemExit("dashboard history daily anchor not found")
    text = text.replace(anchor, helper, 1)

old = '    st.metric("該当履歴", f"{len(hist):,} 行")\n'
new = '    _render_history_analysis_summary(daily_history_text_summary(hist))\n    st.metric("該当履歴", f"{len(hist):,} 行")\n'
if new not in text:
    if old not in text:
        raise SystemExit("daily summary insertion anchor not found")
    text = text.replace(old, new, 1)

old = '    st.metric("該当評価履歴", f"{len(e):,} 行")\n'
new = '    _render_history_analysis_summary(evaluation_history_text_summary(e))\n    st.metric("該当評価履歴", f"{len(e):,} 行")\n'
if new not in text:
    if old not in text:
        raise SystemExit("evaluation summary insertion anchor not found")
    text = text.replace(old, new, 1)

old = '    forward_chart = star_forward_return_summary(star_events)\n    matured_chart = forward_chart.loc[forward_chart["確定件数"] > 0, ["平均リターン(%)"]] if not forward_chart.empty else pd.DataFrame()\n'
new = '    forward_chart = star_forward_return_summary(star_events)\n    all_analysis_signature = _analysis_history_signature(None, None)\n    perf = _cached_condition_performance(str(ROOT), all_analysis_signature, _star_outcomes_signature())\n    _render_history_analysis_summary(star_validation_text_summary(star_events, forward_chart, perf))\n    matured_chart = forward_chart.loc[forward_chart["確定件数"] > 0, ["平均リターン(%)"]] if not forward_chart.empty else pd.DataFrame()\n'
if new not in text:
    if old not in text:
        raise SystemExit("star summary insertion anchor not found")
    text = text.replace(old, new, 1)
late = '    all_analysis_signature = _analysis_history_signature(None, None)\n    perf = _cached_condition_performance(str(ROOT), all_analysis_signature, _star_outcomes_signature())\n'
if text.count(late) > 1:
    first = text.find(late)
    second = text.find(late, first + len(late))
    text = text[:second] + text[second + len(late):]
dashboard.write_text(text, encoding="utf-8")


test = Path("tests/test_history_text_summary.py")
test.write_text(textwrap.dedent('''\
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
'''), encoding="utf-8")


readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
marker = '- 既存の30日・90日・180日実績は保持し、10日・20日・60日はYahoo実績更新等で段階的に補完できます。\n'
addition = marker + '- 「履歴・実績検証」の3画面に、表示中データから件数・評価構成・実績傾向・注意点を短い箇条書きで整理する「分析結果サマリ」を追加しました。外部AI/APIは呼びません。\n'
if addition not in text:
    if marker not in text:
        raise SystemExit("README v0.6.60 marker not found")
    text = text.replace(marker, addition, 1)
readme.write_text(text, encoding="utf-8")

changelog = Path("CHANGELOG.md")
text = changelog.read_text(encoding="utf-8")
marker = '- ◎☆確定件数表示とルール学習側にも同じ欠損列ガードを追加し、旧履歴を削除・再作成せず利用可能にした。\n'
addition = marker + '- 「履歴・実績検証」の日次分析履歴・評価履歴・◎☆実績検証に、表示中データだけで生成する簡潔な分析結果サマリを追加。\n'
if addition not in text:
    if marker not in text:
        raise SystemExit("CHANGELOG v0.6.60 marker not found")
    text = text.replace(marker, addition, 1)
changelog.write_text(text, encoding="utf-8")

current = Path("tasks/CURRENT.md")
text = current.read_text(encoding="utf-8")
marker = '- [x] 実データ再作成を要求せず、回帰テストで後方互換を固定する。\n'
addition = marker + '- [x] 履歴・実績検証の3画面に、表示中データに応じた簡潔な分析結果サマリを表示する。\n'
if addition not in text:
    if marker not in text:
        raise SystemExit("CURRENT v0.6.60 marker not found")
    text = text.replace(marker, addition, 1)
current.write_text(text, encoding="utf-8")
