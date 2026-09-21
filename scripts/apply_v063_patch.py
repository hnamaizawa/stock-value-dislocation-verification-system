from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"marker not found in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/value_dislocation/strategy/criteria.py",
    "from .features import financial_features, price_features\nfrom .scoring import add_valuation_features, score_candidates\n",
    "from .features import financial_features, price_features\nfrom .attribution import add_external_shock_attribution\nfrom .scoring import add_valuation_features, score_candidates\n",
)
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '    relative_filter_enabled = bool(s.get("use_relative_underperformance_filter", True)) and benchmark_mode != "disabled"\n',
    '''    scored["benchmark_return_6m"] = np.nan
    official_mask = scored["benchmark_source"].astype(str).eq("official_topix")
    proxy_mask = scored["benchmark_source"].astype(str).eq("topix_etf_proxy")
    official_returns = _numeric_series(scored, "topix_return_6m", index)
    proxy_returns = _numeric_series(scored, "topix_proxy_return_6m", index)
    scored.loc[official_mask, "benchmark_return_6m"] = official_returns.loc[official_mask]
    scored.loc[proxy_mask, "benchmark_return_6m"] = proxy_returns.loc[proxy_mask]
    scored = add_external_shock_attribution(scored)

    relative_filter_enabled = bool(s.get("use_relative_underperformance_filter", True)) and benchmark_mode != "disabled"
''',
)
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '        if selection_strategy == "value_dislocation":\n            warnings.append("外的要因は未確認")\n',
    '''        attribution = pd.to_numeric(pd.Series([row.get("external_shock_attribution_score")]), errors="coerce").iloc[0]
        if pd.notna(attribution):
            warnings.append(f"外因説明率 {float(attribution):.0f}%（市場・業種価格要因の説明率。因果証明ではない）")
        elif selection_strategy == "value_dislocation":
            warnings.append("外因説明率は市場・業種比較データ不足")
        if selection_strategy == "value_dislocation":
            warnings.append("外的要因は未確認")
''',
)

replace_once(
    "src/value_dislocation/history.py",
    '    "close", "drawdown_52w", "relative_return_6m", "sector_relative_return_6m",\n',
    '    "close", "drawdown_52w", "relative_return_6m", "sector_relative_return_6m",\n    "external_shock_attribution", "external_shock_attribution_score", "company_specific_component_6m",\n',
)
replace_once(
    "src/value_dislocation/history.py",
    '    ("業種中央値への劣後 15%以内", "sector_relative_return_6m", ">=", -0.15),\n',
    '    ("業種中央値への劣後 15%以内", "sector_relative_return_6m", ">=", -0.15),\n    ("外因説明率 50%以上", "external_shock_attribution", ">=", 0.50),\n',
)

replace_once(
    "dashboard.py",
    "from value_dislocation.hypothesis_invalidation import (\n",
    '''from value_dislocation.validation import (
    WalkForwardConfig,
    attribution_outcome_summary,
    walk_forward_summary,
    walk_forward_validation,
)
from value_dislocation.hypothesis_invalidation import (
''',
)
replace_once(
    "dashboard.py",
    '''        quality_cols = st.columns(4)
        quality_cols[0].metric("利益現金化率", _format_pct(row.get("cash_conversion_ratio")))
        quality_cols[1].metric("営業利益率変化", _format_pct(row.get("operating_margin_change_3y")))
        quality_cols[2].metric("会社予想修正", _format_pct(row.get("forecast_revision_rate")))
        quality_cols[3].metric("同業中央値対比", _format_pct(row.get("sector_relative_return_6m")))
''',
    '''        quality_cols = st.columns(5)
        quality_cols[0].metric("利益現金化率", _format_pct(row.get("cash_conversion_ratio")))
        quality_cols[1].metric("営業利益率変化", _format_pct(row.get("operating_margin_change_3y")))
        quality_cols[2].metric("会社予想修正", _format_pct(row.get("forecast_revision_rate")))
        quality_cols[3].metric("同業中央値対比", _format_pct(row.get("sector_relative_return_6m")))
        quality_cols[4].metric("外因説明率", _format_pct(row.get("external_shock_attribution")))
''',
)

walkforward_ui = r'''

def _render_history_walk_forward() -> None:
    st.markdown("### Walk-Forward過去検証")
    st.caption(
        "現在の定量・構造悪化ルールを過去の時点へ再適用し、その後の実績を採点します。"
        "選定には各時点までの価格・開示だけを使い、将来株価は選定完了後の結果評価にのみ使用します。"
        "過去ニュースや人手の外的要因レビューは再現しないため、◎☆全体ではなく定量候補層の検証です。"
    )
    c1, c2, c3 = st.columns(3)
    snapshots = c1.slider("再現時点数", 3, 12, 8, 1, key="wf_snapshots")
    spacing = c2.slider("時点間隔（取引日）", 10, 40, 20, 5, key="wf_spacing")
    controls = c3.slider("類似非選択銘柄数", 3, 10, 5, 1, key="wf_controls")
    st.caption(
        "類似銘柄は同業種を優先し、時価総額・52週下落率・60日ボラ・PER/PBRの業種比が近い"
        "『その時点で選ばれなかった銘柄』から選びます。通常表示だけではデータ取得・再計算しません。"
    )
    if st.button("ローカル過去データでWalk-Forward検証を実行", key="run_walk_forward", type="primary"):
        with st.spinner("過去時点を順番に再現し、類似非選択銘柄と比較しています…"):
            data = load_curated_latest(ROOT)
            cfg = load_config(REAL_CONFIG)
            events = walk_forward_validation(
                data["companies"], data["prices"], data["financials"], cfg,
                settings=WalkForwardConfig(
                    max_snapshots=int(snapshots),
                    spacing_trading_days=int(spacing),
                    controls_per_event=int(controls),
                ),
            )
            st.session_state["walk_forward_validation_events"] = events
        if events.empty:
            st.warning("現在ローカルに保持している過去データでは、検証可能な定量候補イベントを作れませんでした。")
        else:
            st.success(f"Walk-Forward検証を完了しました。候補イベント {len(events):,} 件です。")

    events = st.session_state.get("walk_forward_validation_events")
    if not isinstance(events, pd.DataFrame) or events.empty:
        st.info("『実行』を押すと、ローカル保存済みデータの範囲で過去検証を行います。")
        return

    summary = walk_forward_summary(events)
    dates = pd.to_datetime(events.get("selection_date"), errors="coerce").dropna()
    m1, m2, m3 = st.columns(3)
    m1.metric("候補イベント", f"{len(events):,}件")
    m2.metric("再現時点", f"{events.get('selection_date', pd.Series(dtype=str)).nunique():,}日")
    m3.metric("検証期間", f"{dates.min().date()} ～ {dates.max().date()}" if not dates.empty else "-")

    display = summary.copy()
    for col in ["候補平均", "候補プラス率", "類似非選択平均", "選択効果", "選択効果プラス率"]:
        if col in display.columns:
            display[col] = pd.to_numeric(display[col], errors="coerce") * 100
    st.markdown("#### 現在ルールのWalk-Forward成績")
    st.dataframe(display, width="stretch", hide_index=True)
    chart_cols = [c for c in ["候補平均", "類似非選択平均", "選択効果"] if c in display.columns]
    if chart_cols:
        st.bar_chart(display.set_index("期間")[chart_cols], width="stretch")
    st.caption(
        "選択効果 = 選ばれた候補の実績 − 類似していた非選択銘柄の平均実績。"
        "市場全体が上昇しただけなのか、選択ロジック自体に上乗せ効果があったのかを確認します。"
    )

    attribution = attribution_outcome_summary(events, horizon_days=30)
    if not attribution.empty:
        shown = attribution.copy()
        shown["平均リターン"] = pd.to_numeric(shown["平均リターン"], errors="coerce") * 100
        shown["プラス率"] = pd.to_numeric(shown["プラス率"], errors="coerce") * 100
        st.markdown("#### 外因説明率と30日後実績")
        st.dataframe(shown, width="stretch", hide_index=True)
        st.caption(
            "外因説明率は6カ月下落を『市場＋業種』と『企業固有』に分解した記述統計です。"
            "高いほど市場・業種の下落で説明できる割合が大きいことを示しますが、因果関係の証明ではありません。"
        )

    if st.checkbox("Walk-Forwardイベント詳細を表示", value=False, key="wf_details"):
        details = events.copy()
        pct_cols = [c for c in details.columns if c.startswith(("return_", "control_return_", "selection_edge_"))]
        for col in pct_cols:
            details[col] = pd.to_numeric(details[col], errors="coerce") * 100
        st.dataframe(details.sort_values(["selection_date", "code"], ascending=[False, True]), width="stretch", hide_index=True)
'''
replace_once("dashboard.py", "\n\ndef render_history_and_validation() -> None:\n", walkforward_ui + "\n\ndef render_history_and_validation() -> None:\n")
replace_once(
    "dashboard.py",
    '["日次分析履歴", "評価履歴", "◎☆実績検証"],\n',
    '["日次分析履歴", "評価履歴", "◎☆実績検証", "Walk-Forward検証"],\n',
)
replace_once(
    "dashboard.py",
    '    elif section == "評価履歴":\n        _render_history_evaluations(evaluation)\n    else:\n        _render_history_star_validation(evaluation)\n',
    '    elif section == "評価履歴":\n        _render_history_evaluations(evaluation)\n    elif section == "◎☆実績検証":\n        _render_history_star_validation(evaluation)\n    else:\n        _render_history_walk_forward()\n',
)

replace_once("pyproject.toml", 'version = "0.6.62"', 'version = "0.6.63"')
replace_once("src/value_dislocation/__init__.py", '__version__ = "0.6.62"', '__version__ = "0.6.63"')
replace_once("harness/app_blueprint.yaml", "blueprint_version: 0.6.62", "blueprint_version: 0.6.63")
replace_once(
    "harness/app_blueprint.yaml",
    "- structural_deterioration_value_trap_guard\n",
    "- structural_deterioration_value_trap_guard\n- point_in_time_walk_forward_validation\n- matched_nonselected_control_comparison\n- external_shock_attribution_decomposition\n",
)
replace_once(
    "harness/app_blueprint.yaml",
    "- known_structural_deterioration_must_block_value_dislocation_candidate\n",
    "- known_structural_deterioration_must_block_value_dislocation_candidate\n- walk_forward_selection_must_not_use_future_prices\n- matched_controls_must_exclude_selected_securities\n- external_shock_attribution_must_not_replace_human_event_review\n- walk_forward_validation_must_not_trigger_market_data_fetch\n",
)

readme = Path("README.md").read_text(encoding="utf-8")
readme = readme.replace("Version: **0.6.62**", "Version: **0.6.63**", 1)
marker = "### v0.6.62 構造悪化ガードでバリュートラップを識別\n"
addition = '''### v0.6.63 Walk-Forward・類似非選択比較・外因説明率

- 現在の定量・構造悪化ルールを過去時点へ再適用するpoint-in-time Walk-Forward検証を追加しました。選定完了後にだけ将来株価を結果採点へ使います。
- 各候補に対し、同業種を優先して時価総額・下落率・ボラ・PER/PBRが近い非選択銘柄を最大5社マッチし、候補リターンとの差を「選択効果」として測定します。
- 6カ月騰落を市場・業種・企業固有に分解し、下落のうち市場＋業種要因で説明できる割合を「外因説明率」として0〜100%表示します。因果関係の証明ではなく、人手の外的要因レビューを置き換えません。
- Walk-Forwardは履歴・実績検証から明示実行し、ローカルcertifiedデータだけを使います。画面表示や条件変更でJ-Quants/Yahoo取得は発生しません。

'''
if marker not in readme:
    raise SystemExit("README v0.6.62 marker missing")
Path("README.md").write_text(readme.replace(marker, addition + marker, 1), encoding="utf-8")

changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
Path("CHANGELOG.md").write_text('''## v0.6.63
- point-in-time Walk-Forward過去検証を追加。選定時点より後の価格・開示は選定に使用しない。
- 同業種優先の類似非選択銘柄マッチングを追加し、候補リターンとの差を選択効果として10/20/30/60/90/180日で評価。
- 6カ月騰落を市場・業種・企業固有要因へ分解する外因説明率を追加。因果証明ではなく外的要因レビューを置換しない。
- Walk-Forwardはローカルcertifiedデータの明示実行のみで、追加API取得を行わない。

''' + changelog, encoding="utf-8")

tasks = Path("tasks/CURRENT.md").read_text(encoding="utf-8")
Path("tasks/CURRENT.md").write_text('''## v0.6.63 walk-forward / matched controls / attribution

- [x] point-in-time Walk-Forward検証を追加する。
- [x] 類似非選択銘柄とのリターン比較と選択効果を追加する。
- [x] 市場・業種・企業固有へ分解する外因説明率を追加する。
- [x] 通常表示・条件変更では追加データ取得しない。

''' + tasks, encoding="utf-8")

for path in ["tests/test_package_init.py", "tests/test_sort_performance_and_readme_structure.py"]:
    p = Path(path)
    p.write_text(p.read_text(encoding="utf-8").replace("0.6.62", "0.6.63"), encoding="utf-8")

p = Path("tests/test_history_dashboard.py")
t = p.read_text(encoding="utf-8")
t += '''

def test_walk_forward_validation_is_explicit_and_local_only():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert '"Walk-Forward検証"' in text
    assert 'ローカル過去データでWalk-Forward検証を実行' in text
    assert 'walk_forward_validation(' in text
    validation = Path("src/value_dislocation/validation.py").read_text(encoding="utf-8")
    assert "fetch_yahoo" not in validation
    assert "jquants" not in validation.lower()
'''
p.write_text(t, encoding="utf-8")
