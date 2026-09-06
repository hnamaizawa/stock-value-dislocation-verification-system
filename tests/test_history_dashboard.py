from pathlib import Path

def test_dashboard_has_history_page_and_persists_unified_evaluation():
    text=Path("dashboard.py").read_text(encoding="utf-8")
    assert 'title="履歴・検証"' in text
    assert "upsert_daily_evaluations(ROOT, all_result" in text
    assert "write_star_outcomes(ROOT)" in text
    assert "_cached_condition_performance(" in text


def test_real_pipeline_writes_daily_history_without_extra_fetch():
    text=Path("src/value_dislocation/real_pipeline.py").read_text(encoding="utf-8")
    assert "write_daily_analysis_snapshot(" in text
    assert "write_star_outcomes(root)" in text
    hist=Path("src/value_dislocation/history.py").read_text(encoding="utf-8")
    assert "jquants" not in hist.lower()
    assert "yfinance" not in hist.lower()


def test_history_validation_obeys_yahoo_bulk_limit():
    text=Path("dashboard.py").read_text(encoding="utf-8")
    assert "yahoo_bulk_fetch_allowed(len(star_codes))" in text
    assert "len(star_codes) >= YAHOO_BULK_FETCH_BLOCK_THRESHOLD" in text


def test_history_page_is_registered_in_top_navigation():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert 'HISTORY_PAGE = st.Page(render_history_and_validation, title="履歴・検証"' in text
    assert '[DATA_PAGE, CONDITION_PAGE, STOCK_DETAIL_PAGE, HISTORY_PAGE, SBI_IMPORT_PAGE, DEMO_PAGE, SAFETY_PAGE]' in text


def test_daily_history_search_supports_final_evaluation_filter():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert 'multiselect("当日の最終評価", final_options' in text
    assert "_cached_load_attached_analysis_history(" in text
    assert 'hist["final_evaluation"].astype(str).isin(selected_final)' in text
    assert 'selected_for_review は定量条件の通過有無' in text


def test_history_dashboard_supports_unassessed_reason_and_manual_backfill():
    text=Path("dashboard.py").read_text(encoding="utf-8")
    assert 'multiselect("未評価理由", reason_options' in text
    assert '"Yahoo取得失敗", "Yahoo100件制限で未実施", "旧履歴", "履歴不足／再現不能"' in text
    assert 'f"表示中の未評価 {len(unassessed):,} 件を後から再評価"' in text
    assert "revaluate_unassessed_rows(" in text
    assert "yahoo_bulk_fetch_allowed" in text
    assert 'evaluation_status = "後日補完"' not in text  # status is produced by the pure history helper


def test_history_dashboard_supports_slow_resumable_batches_over_100_codes():
    text=Path("dashboard.py").read_text(encoding="utf-8")
    assert '"低速バッチの1回あたり銘柄数"' in text
    assert 'select_slow_revaluation_batch(unassessed' in text
    assert '"低速バッチ再評価を開始・続行（次の' in text
    assert 'time.sleep(SLOW_REVALUATION_DELAY_SECONDS)' in text
    assert 'upsert_daily_evaluations(ROOT, group' in text
    assert '通常の一括再評価は100銘柄以上では開始しません' in text


def test_history_dashboard_supports_slow_loop_until_all_codes_attempted_once():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert '"全未評価を最後まで自動ループする"' in text
    assert 'f"全件を低速ループ再評価（{len(unique_codes):,}銘柄）"' in text
    assert 'for idx, code in enumerate(unique_codes, start=1):' in text
    assert 'if idx % batch_size_value == 0:' in text
    assert 'time.sleep(SLOW_REVALUATION_BATCH_PAUSE_SECONDS)' in text
    assert 'upsert_daily_evaluations(ROOT, group' in text
    assert '取得失敗銘柄は同じ実行内で無限再試行しません' in text
    assert 'disabled=(not loop_confirm or not unique_codes)' in text


def test_history_dashboard_uses_lazy_sections_cache_and_pagination():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "st.segmented_control(" in text
    assert "st.tabs([\"日次分析履歴\", \"評価履歴\", \"◎☆実績検証\"])" not in text
    assert "_cached_load_attached_analysis_history(" in text
    assert "_cached_load_evaluation_history(" in text
    assert "_cached_load_star_outcomes(" in text
    assert "_cached_condition_performance(" in text
    assert "_history_page_slice(" in text
    assert 'button("Yahooで30/90/180日実績を更新"' in text
    assert "画面を開いただけではYahooへアクセスしません" in text


def test_history_module_can_load_saved_star_outcomes_without_rebuild():
    text = Path("src/value_dislocation/history.py").read_text(encoding="utf-8")
    assert "def load_star_outcomes(" in text
    assert 'star_outcomes.csv.gz' in text


def test_star_validation_reconciles_all_events_and_has_explicit_pager():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "reconcile_star_outcomes(evaluation, saved_star_events)" in text
    assert 'st.markdown("#### ◎☆銘柄サマリ（同一銘柄は1行）")' in text
    assert "summarize_star_outcomes_by_code(star_events)" in text
    assert 'button("◀ 前へ"' in text
    assert 'button("次へ ▶"' in text
    assert '全 {len(frame):,}件を表示対象にしています' in text
    assert 'default_size=50, compact_sizes=True' in text
    assert 'st.segmented_control("並び順", ["最新◎☆日の新しい順", "初回◎☆日の古い順"]' in text
    assert 'checkbox("◎☆開始イベントを個別表示する"' in text


def test_history_dashboard_separates_non_candidates_from_unassessed():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert 'status_options = ["当日評価済み", "後日補完", "未評価", "評価対象外"]' in text
    assert '"定量候補外"' in text
    assert '定量候補外は『評価対象外』として扱い、未評価件数には含めません' in text
    hist = Path("src/value_dislocation/history.py").read_text(encoding="utf-8")
    assert 'EVALUATION_STATUS_NOT_APPLICABLE = "評価対象外"' in hist
    assert 'UNASSESSED_REASON_NOT_SELECTED = "定量候補外"' in hist


def test_history_stock_tables_use_same_button_navigation_as_candidates():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "def _render_history_stock_buttons(" in text
    assert 'selection_mode="single-row"' not in text
    assert 'on_select="rerun"' not in text
    assert 'button(display_code' in text
    assert 'button(name or display_code' in text
    assert '_open_stock_detail(code)' in text
    assert '_render_history_stock_buttons(page, "daily_history")' in text
    assert '_render_history_stock_buttons(evaluation_page, "evaluation_history")' in text
    assert '_render_history_stock_buttons(summary_page, "star_summary")' in text
    assert '_render_history_stock_buttons(event_page, "star_events_detail")' in text
    assert '銘柄コードまたは企業名ボタンをクリックすると、個別銘柄検索へ移動します。' in text


def test_history_button_lists_keep_paging_compact_for_performance():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert '_history_page_slice(sorted_hist, "daily_history", default_size=50, compact_sizes=True)' in text
    assert '_history_page_slice(sorted_e, "evaluation_history", default_size=50, compact_sizes=True)' in text
    assert 'with st.expander("現在ページの全列を表形式で確認"' in text
