from pathlib import Path


def test_clickable_tables_restore_column_header_sorting():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "def _sorted_clickable_table_frame(" in text
    assert "def _sortable_header_button(" in text
    assert "クリックで昇順／降順を切り替えます。" in text
    assert 'marker = " ▲" if active_ascending else " ▼"' in text
    assert 'marker = " ↕"' in text
    assert '_sorted_clickable_table_frame(result, "unified_candidates")' in text
    assert '_sortable_header_button(col, label, field, "unified_candidates")' in text
    assert '_sorted_clickable_table_frame(shortlist, "clickable_candidates")' in text


def test_history_tables_sort_before_pagination_and_keep_navigation_buttons():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    start = text.index("def _render_history_sortable_stock_table(")
    end = text.index("def _render_clickable_candidates(", start)
    block = text[start:end]
    assert block.index("_sorted_clickable_table_frame(frame, key)") < block.index("page = _history_page_slice(")
    assert "_render_history_stock_buttons(page, key)" in block
    assert '_sortable_header_button(header[0], "コード", "code", key)' in text
    assert '_sortable_header_button(header[1], "企業名", "name", key)' in text
    assert '_render_history_sortable_stock_table(sorted_hist, "daily_history")' in text
    assert '_render_history_sortable_stock_table(sorted_e, "evaluation_history")' in text
    assert '_render_history_sortable_stock_table(summary, "star_summary")' in text
    assert '_render_history_sortable_stock_table(event_show, "star_events_detail")' in text
    history_start = text.index("def _render_history_stock_buttons(")
    history_end = text.index("@st.fragment\ndef _render_history_sortable_stock_table(", history_start)
    history_block = text[history_start:history_end]
    assert history_block.count('.link_button(') == 2
    assert '_stock_detail_new_tab_url(code)' in history_block
    assert '_open_stock_detail(code)' not in history_block
