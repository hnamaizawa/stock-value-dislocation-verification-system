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
    assert text.index('_sorted_clickable_table_frame(sorted_hist, "daily_history")') < text.index('_history_page_slice(sorted_hist, "daily_history"')
    assert text.index('_sorted_clickable_table_frame(sorted_e, "evaluation_history")') < text.index('_history_page_slice(sorted_e, "evaluation_history"')
    assert text.index('_sorted_clickable_table_frame(summary, "star_summary")') < text.index('_history_page_slice(summary, "star_summary"')
    assert text.index('_sorted_clickable_table_frame(event_show, "star_events_detail")') < text.index('_history_page_slice(event_show, "star_events_detail"')
    assert '_sortable_header_button(header[0], "コード", "code", key)' in text
    assert '_sortable_header_button(header[1], "企業名", "name", key)' in text
    assert 'button(display_code' in text
    assert 'button(name or display_code' in text
    assert '_open_stock_detail(code)' in text
