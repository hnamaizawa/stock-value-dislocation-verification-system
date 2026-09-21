from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one occurrence, found {count}: {old[:80]!r}")
    write(path, text.replace(old, new, 1))


def prepend(path: str, text_to_add: str) -> None:
    write(path, text_to_add + read(path))


# --- Point-in-time feature attribution -------------------------------------------------
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    "from .features import financial_features, price_features\nfrom .scoring import add_valuation_features, score_candidates\n",
    "from .features import financial_features, price_features\nfrom .attribution import add_external_shock_attribution\nfrom .scoring import add_valuation_features, score_candidates\n",
)
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '    merged["sector_relative_return_6m"] = merged["return_6m"] - merged["sector_return_6m_median"]\n    merged.loc[merged["sector_peer_count_6m"] < 5, "sector_relative_return_6m"] = np.nan\n    for key, value in EVENT_PLACEHOLDERS.items():\n',
    '    merged["sector_relative_return_6m"] = merged["return_6m"] - merged["sector_return_6m_median"]\n    merged.loc[merged["sector_peer_count_6m"] < 5, "sector_relative_return_6m"] = np.nan\n    merged = add_external_shock_attribution(merged)\n    for key, value in EVENT_PLACEHOLDERS.items():\n',
)

# --- Persist attribution in point-in-time history --------------------------------------
replace_once(
    "src/value_dislocation/history.py",
    '    "close", "drawdown_52w", "relative_return_6m", "sector_relative_return_6m",\n    "sales_cagr_3y", "operating_margin", "operating_margin_change_3y",\n',
    '    "close", "drawdown_52w", "relative_return_6m", "sector_relative_return_6m",\n    "external_shock_attribution_score", "attribution_market_return_6m",\n    "attribution_sector_return_6m", "attribution_sector_component_6m", "attribution_company_component_6m",\n    "sales_cagr_3y", "operating_margin", "operating_margin_change_3y",\n',
)
replace_once(
    "src/value_dislocation/history.py",
    '    ("業種中央値への劣後 15%以内", "sector_relative_return_6m", ">=", -0.15),\n    ("予想配当利回り 3%以上", "forecast_dividend_yield", ">=", 0.03),\n',
    '    ("業種中央値への劣後 15%以内", "sector_relative_return_6m", ">=", -0.15),\n    ("外因説明率 60%以上", "external_shock_attribution_score", ">=", 60.0),\n    ("予想配当利回り 3%以上", "forecast_dividend_yield", ">=", 0.03),\n',
)

# --- Dashboard integration --------------------------------------------------------------
replace_once(
    "dashboard.py",
    'from value_dislocation.strategy.criteria import (\n    apply_quantitative_criteria,\n    copy_with_screen_overrides,\n    prepare_quantitative_universe,\n    screening_funnel,\n    shortlist_from_table,\n)\nfrom value_dislocation.strategy.profiles import (\n',
    'from value_dislocation.strategy.criteria import (\n    apply_quantitative_criteria,\n    copy_with_screen_overrides,\n    prepare_quantitative_universe,\n    screening_funnel,\n    shortlist_from_table,\n)\nfrom value_dislocation.strategy_validation import run_walk_forward_validation\nfrom value_dislocation.strategy.profiles import (\n',
)
replace_once(
    "dashboard.py",
    '        "cash_conversion_ratio", "operating_margin_change_3y",\n        "forecast_revision_rate", "sector_relative_return_6m",\n',
    '        "cash_conversion_ratio", "operating_margin_change_3y",\n        "forecast_revision_rate", "sector_relative_return_6m",\n        "external_shock_attribution_score",\n',
)
replace_once(
    "dashboard.py",
    '        quality_cols = st.columns(4)\n        quality_cols[0].metric("利益現金化率", _format_pct(row.get("cash_conversion_ratio")))\n        quality_cols[1].metric("営業利益率変化", _format_pct(row.get("operating_margin_change_3y")))\n        quality_cols[2].metric("会社予想修正", _format_pct(row.get("forecast_revision_rate")))\n        quality_cols[3].metric("同業中央値対比", _format_pct(row.get("sector_relative_return_6m")))\n',
    '        quality_cols = st.columns(5)\n        quality_cols[0].metric("利益現金化率", _format_pct(row.get("cash_conversion_ratio")))\n        quality_cols[1].metric("営業利益率変化", _format_pct(row.get("operating_margin_change_3y")))\n        quality_cols[2].metric("会社予想修正", _format_pct(row.get("forecast_revision_rate")))\n        quality_cols[3].metric("同業中央値対比", _format_pct(row.get("sector_relative_return_6m")))\n        attribution_value = pd.to_numeric(pd.Series([row.get("external_shock_attribution_score")]), errors="coerce").iloc[0]\n        quality_cols[4].metric("外因説明率", f"{float(attribution_value):.1f}%" if not pd.isna(attribution_value) else "-")\n',
)

strategy_renderer = r'''

def _render_strategy_validation() -> None:
    bundle = _bundle_or_none()
    if bundle is None:
        st.warning("先に『データ更新』で実データを取得してください。")
        return

    st.subheader("戦略検証：Walk-Forward / 類似非選択銘柄 / 外因説明率")
    st.caption(
        "既存のcuratedデータだけを使い、過去時点の定量条件・構造悪化ガード・反転確認を再計算します。"
        "現在のニュースや現在の外的要因レビューを過去へ遡って使わないため、完全な過去◎☆再現ではありません。"
        "J-Quants / Yahooへの追加アクセスも行いません。"
    )

    p1, p2, p3, p4 = st.columns(4)
    step_days = p1.selectbox(
        "評価間隔（営業日）", [1, 5, 10, 20], index=1, key="wf_step_days",
        help="過去の全営業日を毎回再計算すると重いため、何営業日おきに再現するかを指定します。",
    )
    max_dates = p2.selectbox(
        "最大評価日数", [10, 20, 40, 60], index=1, key="wf_max_dates",
        help="直近側から最大何評価日をWalk-Forwardするかを指定します。",
    )
    event_gap = p3.selectbox(
        "同一銘柄イベント間隔（日）", [10, 20, 30, 60], index=1, key="wf_event_gap",
        help="同じシグナルが連日出たときに同一事象を重複カウントしすぎないための間隔です。",
    )
    peer_count = p4.selectbox(
        "類似非選択銘柄数", [3, 5, 7, 10], index=1, key="wf_peer_count",
        help="同業種を優先し、時価総額・下落率・PER/PBR相対値などが近い非選択銘柄を対照群にします。",
    )

    st.caption(
        "52週高値からの下落率を過去時点で崩さず再現するため、標準では評価日前に252営業日以上ある日だけを対象にします。"
        "ローカル株価履歴が短い場合はWalk-Forward可能な日数も少なくなります。"
    )

    if st.button("ローカル履歴でWalk-Forward検証を実行", type="primary", key="run_walk_forward_validation"):
        config = load_config(REAL_CONFIG)
        data = bundle["data"]
        with st.spinner("未来情報を使わず過去時点を順番に再計算しています…"):
            result = run_walk_forward_validation(
                data["companies"],
                data["prices"],
                data["financials"],
                config,
                step_trading_days=int(step_days),
                max_evaluation_dates=int(max_dates),
                event_gap_days=int(event_gap),
                peer_count=int(peer_count),
                minimum_history_observations=252,
                horizons=STAR_OUTCOME_HORIZONS,
            )
        st.session_state["strategy_validation_result"] = result
        st.success("Walk-Forward検証を完了しました。結果はこのブラウザセッション内に保持します。")

    result = st.session_state.get("strategy_validation_result")
    if not isinstance(result, dict):
        st.info("上のボタンを押すと、現在のv0.6.63ルールを過去時点へ再適用して検証します。")
        return

    coverage = result.get("coverage", {}) or {}
    events = result.get("events", pd.DataFrame())
    summary = result.get("summary", pd.DataFrame())

    if coverage.get("reason"):
        st.warning(str(coverage.get("reason")))
        st.caption(
            f"利用可能営業日={coverage.get('available_trading_dates', 0)} / "
            f"必要過去日数={coverage.get('minimum_history_observations', 252)}。"
            "この場合も今後の前向き10/20/30/60/90/180日実績検証は継続できます。"
        )
        return

    st.markdown("#### 検証カバレッジ")
    coverage_cols = st.columns(5)
    coverage_cols[0].metric("評価日", f"{int(coverage.get('evaluation_dates', 0)):,}")
    coverage_cols[1].metric("定量候補出現", f"{int(coverage.get('quantitative_candidate_occurrences', 0)):,}")
    coverage_cols[2].metric("反転確認出現", f"{int(coverage.get('reversal_candidate_occurrences', 0)):,}")
    coverage_cols[3].metric("独立イベント", f"{int(coverage.get('deduplicated_events', 0)):,}")
    coverage_cols[4].metric("価格履歴営業日", f"{int(coverage.get('available_trading_dates', 0)):,}")
    st.caption(
        f"価格期間: {coverage.get('price_start', '-')} ～ {coverage.get('price_end', '-')} / "
        f"評価期間: {coverage.get('evaluation_start', '-')} ～ {coverage.get('evaluation_end', '-')}。"
        f"対象範囲: {coverage.get('scope', '')}"
    )

    if not isinstance(summary, pd.DataFrame) or summary.empty:
        st.info("集計できるWalk-Forwardイベントがありませんでした。条件または利用可能な履歴期間を確認してください。")
        return

    display = summary.copy()
    pct_columns = ["候補平均", "候補中央値", "候補プラス率", "類似非選択平均", "選択超過平均", "対照超過率"]
    for column in pct_columns:
        if column in display.columns:
            display[column] = pd.to_numeric(display[column], errors="coerce") * 100.0

    st.markdown("#### Walk-Forward実績と類似非選択銘柄比較")
    st.caption(
        "『選択超過平均』は候補リターン－同日に似ていた非選択銘柄の平均です。"
        "プラスなら、市場全体の上昇だけでは説明しにくい選択効果の候補になります。"
    )
    st.dataframe(display, width="stretch", hide_index=True)
    chart_columns = [c for c in ["候補平均", "類似非選択平均", "選択超過平均"] if c in display.columns]
    chart = display.set_index("期間")[chart_columns].dropna(how="all") if chart_columns else pd.DataFrame()
    if not chart.empty:
        st.bar_chart(chart, width="stretch")
        st.caption("グラフの単位は%。確定していない期間は集計から除外しています。")

    if isinstance(events, pd.DataFrame) and not events.empty:
        attribution = pd.to_numeric(events.get("external_shock_attribution_score"), errors="coerce").dropna()
        st.markdown("#### External Shock Attribution（外因説明率）")
        st.caption(
            "6か月下落のうち同業種中央値の下落でも説明できる割合です。高いほど市場・業種要因と整合し、"
            "低いほど企業固有の弱さが大きい可能性があります。因果関係を証明する指標ではありません。"
        )
        attr_cols = st.columns(4)
        attr_cols[0].metric("算出可能イベント", f"{len(attribution):,}")
        attr_cols[1].metric("平均外因説明率", f"{float(attribution.mean()):.1f}%" if len(attribution) else "-")
        attr_cols[2].metric("外因優勢（70%以上）", f"{int((attribution >= 70).sum()):,}" if len(attribution) else "0")
        attr_cols[3].metric("企業固有優勢（40%未満）", f"{int((attribution < 40).sum()):,}" if len(attribution) else "0")
        if len(attribution):
            buckets = pd.DataFrame(
                {
                    "件数": [
                        int((attribution < 40).sum()),
                        int(((attribution >= 40) & (attribution < 70)).sum()),
                        int((attribution >= 70).sum()),
                    ]
                },
                index=["企業固有優勢 <40%", "混合 40-70%", "外因優勢 >=70%"],
            )
            st.bar_chart(buckets, width="stretch")

        if st.checkbox("Walk-Forwardイベント詳細を表示", value=False, key="show_walk_forward_events"):
            event_show = events.copy()
            for horizon in STAR_OUTCOME_HORIZONS:
                for prefix in ("return", "peer_return", "excess_return"):
                    column = f"{prefix}_{horizon}d" if prefix != "peer_return" else f"peer_return_{horizon}d_avg"
                    if column in event_show.columns:
                        event_show[column] = pd.to_numeric(event_show[column], errors="coerce") * 100.0
            for column in (
                "return_20d_at_entry", "attribution_market_return_6m", "attribution_sector_return_6m",
                "attribution_sector_component_6m", "attribution_company_component_6m",
            ):
                if column in event_show.columns:
                    event_show[column] = pd.to_numeric(event_show[column], errors="coerce") * 100.0
            st.dataframe(event_show.sort_values(["validation_date", "code"], ascending=[False, True]), width="stretch", hide_index=True)
            st.caption("リターン系の列は%表示、external_shock_attribution_score は0～100のスコアです。")
'''
replace_once(
    "dashboard.py",
    "\ndef render_history_and_validation() -> None:\n",
    strategy_renderer + "\n\ndef render_history_and_validation() -> None:\n",
)
replace_once(
    "dashboard.py",
    '        ["日次分析履歴", "評価履歴", "◎☆実績検証"],\n',
    '        ["日次分析履歴", "評価履歴", "◎☆実績検証", "戦略検証"],\n',
)
replace_once(
    "dashboard.py",
    '    if section == "日次分析履歴":\n        _render_history_daily(evaluation_signature)\n    elif section == "評価履歴":\n        _render_history_evaluations(evaluation)\n    else:\n        _render_history_star_validation(evaluation)\n',
    '    if section == "日次分析履歴":\n        _render_history_daily(evaluation_signature)\n    elif section == "評価履歴":\n        _render_history_evaluations(evaluation)\n    elif section == "◎☆実績検証":\n        _render_history_star_validation(evaluation)\n    else:\n        _render_strategy_validation()\n',
)

# --- Harness contract -------------------------------------------------------------------
replace_once(
    "scripts/harness_check.py",
    '    "src/value_dislocation/history.py",\n]\n',
    '    "src/value_dislocation/history.py",\n    "src/value_dislocation/strategy/attribution.py",\n    "src/value_dislocation/strategy_validation.py",\n    "docs/22_STRATEGY_VALIDATION.md",\n]\n',
)
validation_check = r'''

def check_strategy_validation(root: Path) -> CheckResult:
    validation_path = root / "src/value_dislocation/strategy_validation.py"
    attribution_path = root / "src/value_dislocation/strategy/attribution.py"
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    validation = validation_path.read_text(encoding="utf-8") if validation_path.exists() else ""
    attribution = attribution_path.read_text(encoding="utf-8") if attribution_path.exists() else ""
    required_validation = [
        "run_walk_forward_validation", "reversal_confirmation_snapshot",
        "minimum_history_observations", "match_similar_nonselected_peers",
        "peer_return_", "excess_return_", "historical_slice",
    ]
    required_attribution = [
        "external_shock_attribution_score", "attribution_market_return_6m",
        "attribution_sector_component_6m", "attribution_company_component_6m",
        "sector_peer_count_6m",
    ]
    required_dashboard = [
        "戦略検証", "Walk-Forward", "類似非選択銘柄", "External Shock Attribution", "外因説明率",
    ]
    missing = [x for x in required_validation if x not in validation]
    missing += [x for x in required_attribution if x not in attribution]
    missing += [x for x in required_dashboard if x not in dashboard]
    forbidden_network = [x for x in ("fetch_yahoo", "jquants", "requests.get", "httpx") if x in validation.lower()]
    passed = validation_path.exists() and attribution_path.exists() and not missing and not forbidden_network
    return CheckResult(
        "strategy_validation",
        passed,
        json.dumps({"missing": missing, "network_terms": forbidden_network}, ensure_ascii=False),
    )
'''
replace_once(
    "scripts/harness_check.py",
    "\ndef check_dividend_screening(root: Path) -> CheckResult:\n",
    validation_check + "\n\ndef check_dividend_screening(root: Path) -> CheckResult:\n",
)
replace_once(
    "scripts/harness_check.py",
    "        check_large_data_navigation_performance(root),\n        check_dividend_screening(root),\n",
    "        check_large_data_navigation_performance(root),\n        check_strategy_validation(root),\n        check_dividend_screening(root),\n",
)

# --- Blueprint --------------------------------------------------------------------------
replace_once("harness/app_blueprint.yaml", "blueprint_version: 0.6.62\n", "blueprint_version: 0.6.63\n")
replace_once(
    "harness/app_blueprint.yaml",
    "- structural_deterioration_value_trap_guard\n- legacy_vs_reversal_star_outcome_comparison\n",
    "- structural_deterioration_value_trap_guard\n- point_in_time_walk_forward_strategy_validation\n- matched_nonselected_peer_benchmark\n- external_shock_market_sector_company_attribution\n- legacy_vs_reversal_star_outcome_comparison\n",
)
replace_once(
    "harness/app_blueprint.yaml",
    "- missing_structural_guard_metric_must_warn_not_fabricate_failure\n- legacy_star_eligibility_must_remain_comparable_after_rule_change\n",
    "- missing_structural_guard_metric_must_warn_not_fabricate_failure\n- walk_forward_must_not_use_future_market_or_financial_data\n- walk_forward_must_not_retrofit_human_external_event_review\n- matched_control_must_exclude_selected_security\n- external_attribution_must_require_sufficient_sector_peers\n- legacy_star_eligibility_must_remain_comparable_after_rule_change\n",
)
replace_once(
    "harness/app_blueprint.yaml",
    "- src/value_dislocation/strategy/criteria.py\n- src/value_dislocation/strategy/profiles.py\n",
    "- src/value_dislocation/strategy/criteria.py\n- src/value_dislocation/strategy/attribution.py\n- src/value_dislocation/strategy_validation.py\n- src/value_dislocation/strategy/profiles.py\n",
)
replace_once(
    "harness/app_blueprint.yaml",
    "- docs/21_STRUCTURAL_DETERIORATION_GUARDS.md\n",
    "- docs/21_STRUCTURAL_DETERIORATION_GUARDS.md\n- docs/22_STRATEGY_VALIDATION.md\n",
)

# --- Version and docs -------------------------------------------------------------------
replace_once("pyproject.toml", 'version = "0.6.62"', 'version = "0.6.63"')
replace_once("src/value_dislocation/__init__.py", '__version__ = "0.6.62"', '__version__ = "0.6.63"')
replace_once("tests/test_package_init.py", 'assert value_dislocation.__version__ == "0.6.62"', 'assert value_dislocation.__version__ == "0.6.63"')
replace_once("tests/test_sort_performance_and_readme_structure.py", 'assert lines[2] == "Version: **0.6.62**"', 'assert lines[2] == "Version: **0.6.63**"')
replace_once("README.md", "Version: **0.6.62**", "Version: **0.6.63**")
replace_once(
    "README.md",
    "### v0.6.62 構造悪化ガードでバリュートラップを識別\n",
    "### v0.6.63 戦略の自己検証を強化\n\n"
    "- ローカルcuratedデータだけで、過去時点までに存在した株価・開示済み財務情報を使うPoint-in-time Walk-Forward検証を追加しました。人手の外的要因レビューや現在のニュースを過去へ遡って使いません。\n"
    "- Walk-Forward候補ごとに、同業種を優先して時価総額・下落率・PER/PBR相対値等が近い非選択銘柄を対照群にし、候補リターンと類似非選択平均との差（選択超過）を10/20/30/60/90/180日で比較します。\n"
    "- 6か月騰落率を市場・業種・企業固有の3成分へ分解し、同業種下落で説明できる割合を0～100の『外因説明率』として追加しました。5社以上の同業比較がない場合は算出しません。\n"
    "- 『履歴・実績検証』に『戦略検証』画面を追加。検証は明示ボタンでのみ実行し、J-Quants/Yahooへの追加アクセスは行いません。\n"
    "- 外因説明率はv0.6.63では新しいhard filterにせず、Walk-Forwardと前向き実績を蓄積してから閾値化を判断します。\n\n"
    "### v0.6.62 構造悪化ガードでバリュートラップを識別\n",
)
prepend(
    "CHANGELOG.md",
    "## v0.6.63\n"
    "- Point-in-time Walk-Forward検証を追加し、過去時点の定量条件・構造悪化ガード・反転確認を未来情報なしで再現。\n"
    "- 同業種を優先する類似非選択銘柄のmatched controlを作り、10/20/30/60/90/180日の選択超過リターンを集計。\n"
    "- 6か月騰落を市場・業種・企業固有へ分解し、同業種下落で説明できる割合を外因説明率0～100として追加。\n"
    "- 履歴・実績検証へ『戦略検証』画面を追加。ローカルcuratedデータのみを利用し、画面実行で追加API取得を発生させない。\n"
    "- 人手の外的要因レビューや現在のニュースはWalk-Forwardへ遡及適用せず、完全な過去◎☆と誤認しない設計を固定。\n\n",
)
prepend(
    "tasks/CURRENT.md",
    "## v0.6.63 strategy validation\n\n"
    "- [x] 過去時点の情報だけで定量＋構造悪化＋反転確認を再現するWalk-Forward検証を追加する。\n"
    "- [x] 同業種を優先する類似非選択銘柄と将来リターンを比較し、選択超過を測定する。\n"
    "- [x] 市場・業種・企業固有へ6か月騰落を分解し、外因説明率を追加する。\n"
    "- [x] 人手レビュー/現在ニュースを過去へ遡って使わず、未来情報混入を防ぐ。\n"
    "- [x] 戦略検証は明示実行のみとし、追加API取得を行わない。\n\n",
)

print("v0.6.63 patch applied")
