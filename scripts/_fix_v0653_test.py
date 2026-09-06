from pathlib import Path

Path("tests/test_sort_performance_and_readme_structure.py").write_text(
    '''from pathlib import Path


def test_sort_headers_use_callback_without_explicit_second_rerun():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "def _toggle_sort_state(" in text
    assert "on_click=_toggle_sort_state" in text
    assert "args=(key, field)" in text
    start = text.index("def _sortable_header_button(")
    end = text.index("def _render_history_stock_buttons(", start)
    block = text[start:end]
    assert "st.rerun()" not in block


def test_sortable_tables_are_fragment_scoped():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert text.count("@st.fragment") >= 3
    assert "def _render_history_sortable_stock_table(" in text
    assert "def _render_clickable_candidates(" in text
    assert "def _render_unified_candidate_table(" in text
    assert "_render_unified_candidate_table(result, active_mode=active_mode)" in text
    assert '_render_history_sortable_stock_table(sorted_hist, "daily_history")' in text
    assert '_render_history_sortable_stock_table(sorted_e, "evaluation_history")' in text
    assert '_render_history_sortable_stock_table(summary, "star_summary")' in text
    assert '_render_history_sortable_stock_table(event_show, "star_events_detail")' in text


def test_readme_has_single_top_level_version_history_in_descending_order():
    readme = Path("README.md").read_text(encoding="utf-8")
    lines = readme.splitlines()
    assert lines[0] == "# Stock Value Dislocation Verification System"
    assert lines[2] == "Version: **0.6.53**"
    assert readme.count("## 開発履歴（新しい順）") == 1
    assert "Version: **0.6.51**" not in readme
    versions = [
        "### v0.6.53", "### v0.6.52", "### v0.6.51", "### v0.6.50",
        "### v0.6.23", "### v0.6.19", "### v0.6.18", "### v0.6.12",
        "### v0.6.8", "### v0.6.6", "### v0.6.5", "### v0.6.4",
        "### v0.6.3", "### v0.6.2", "### v0.6.1", "### v0.6.0",
        "### v0.5.10", "### v0.5.8", "### v0.5.6", "### v0.5.3",
        "### v0.5.0", "### v0.4.0", "### v0.3.4", "### v0.3.3", "### v0.3.2",
    ]
    positions = [readme.index(version) for version in versions]
    assert positions == sorted(positions)
    assert readme.index("## 開発履歴（新しい順）") < readme.index("## Windows / WSL での利用")
''',
    encoding="utf-8",
)
