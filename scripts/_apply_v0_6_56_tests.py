from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "tests/test_history_dashboard.py",
    '''def test_history_stock_tables_use_same_button_navigation_as_candidates():\n    text = Path("dashboard.py").read_text(encoding="utf-8")\n    assert "def _render_history_stock_buttons(" in text\n    assert 'selection_mode="single-row"' not in text\n    assert 'on_select="rerun"' not in text\n    assert 'button(display_code' in text\n    assert 'button(name or display_code' in text\n    assert '_open_stock_detail(code)' in text\n    assert '_render_history_stock_buttons(page, key)' in text\n    assert '_render_history_sortable_stock_table(sorted_hist, "daily_history")' in text\n    assert '_render_history_sortable_stock_table(sorted_e, "evaluation_history")' in text\n    assert '_render_history_sortable_stock_table(summary, "star_summary")' in text\n    assert '_render_history_sortable_stock_table(event_show, "star_events_detail")' in text\n    assert '銘柄コードまたは企業名ボタンをクリックすると、個別銘柄検索へ移動します。' in text\n''',
    '''def test_history_stock_tables_open_stock_search_in_new_tab_and_keep_history_intact():\n    text = Path("dashboard.py").read_text(encoding="utf-8")\n    start = text.index("def _render_history_stock_buttons(")\n    end = text.index("@st.fragment\\ndef _render_history_sortable_stock_table(", start)\n    history_block = text[start:end]\n    assert 'selection_mode="single-row"' not in history_block\n    assert 'on_select="rerun"' not in history_block\n    assert '_history_stock_detail_url(code)' in history_block\n    assert history_block.count('.link_button(') == 2\n    assert '_open_stock_detail(code)' not in history_block\n    assert '個別銘柄検索を新しいタブで開きます' in history_block\n    assert '元の履歴一覧はそのまま残ります' in history_block\n    assert 'st.context.url' in text\n    assert 'st.query_params.get("code", "")' in text\n    assert 'url_path=STOCK_DETAIL_URL_PATH' in text\n    assert '_render_history_stock_buttons(page, key)' in text\n    assert '_render_history_sortable_stock_table(sorted_hist, "daily_history")' in text\n    assert '_render_history_sortable_stock_table(sorted_e, "evaluation_history")' in text\n    assert '_render_history_sortable_stock_table(summary, "star_summary")' in text\n    assert '_render_history_sortable_stock_table(event_show, "star_events_detail")' in text\n\n\ndef test_candidate_lists_keep_existing_same_tab_navigation():\n    text = Path("dashboard.py").read_text(encoding="utf-8")\n    candidate_start = text.index("def _render_clickable_candidates(")\n    candidate_end = text.index("@st.fragment\\ndef _render_unified_candidate_table(", candidate_start)\n    candidate_block = text[candidate_start:candidate_end]\n    unified_start = text.index("def _render_unified_candidate_table(")\n    unified_end = text.index("def _render_latest_candidate_trends(", unified_start)\n    unified_block = text[unified_start:unified_end]\n    assert '_open_stock_detail(code)' in candidate_block\n    assert '_open_stock_detail(str(item["raw_code"]))' in unified_block\n    assert 'st.switch_page(STOCK_DETAIL_PAGE)' in text\n''',
)
replace_once(
    "tests/test_sortable_clickable_tables.py",
    '''    assert 'button(display_code' in text\n    assert 'button(name or display_code' in text\n    assert '_open_stock_detail(code)' in text\n''',
    '''    history_start = text.index("def _render_history_stock_buttons(")\n    history_end = text.index("@st.fragment\\ndef _render_history_sortable_stock_table(", history_start)\n    history_block = text[history_start:history_end]\n    assert history_block.count('.link_button(') == 2\n    assert '_history_stock_detail_url(code)' in history_block\n    assert '_open_stock_detail(code)' not in history_block\n''',
)
replace_once("tests/test_package_init.py", 'value_dislocation.__version__ == "0.6.55"', 'value_dislocation.__version__ == "0.6.56"')
replace_once("tests/test_sort_performance_and_readme_structure.py", 'assert lines[2] == "Version: **0.6.55**"', 'assert lines[2] == "Version: **0.6.56**"')
replace_once(
    "tests/test_sort_performance_and_readme_structure.py",
    '    versions = [\n        "### v0.6.55 履歴画面の generic timedelta 警告修正",',
    '    versions = [\n        "### v0.6.56 履歴一覧から個別銘柄を新しいタブで確認",\n        "### v0.6.55 履歴画面の generic timedelta 警告修正",',
)
print("test patch applied")
