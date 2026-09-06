from pathlib import Path

# New v0.6.53 regression tests.
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
        "### v0.6.53 ソート高速化・README再構成",
        "### v0.6.52 一覧表の列クリックソート復活",
        "### v0.6.51 Streamlit 1.53.0 互換性修正",
        "### v0.6.50 パステルモード強調",
        "### v0.6.23 運用上限",
        "### v0.6.19 やわらかパステルテーマ強化",
        "### v0.6.18 画面テーマと2種類の抽出ルール",
        "### v0.6.12 外的要因レビューと最新市場鮮度",
        "### v0.6.8 見える化",
        "### v0.6.6 直感判定と買い検討価格帯",
        "### v0.6.5 NumPy timedelta警告の完全修正",
        "### v0.6.4 NumPy timedelta警告の修正",
        "### v0.6.3 パッチ整合性修正",
        "### v0.6.2 最新株価によるトレンド再判定",
        "### v0.6.1 トレンド・売却判断",
        "### v0.6.0 購入判断の整理",
        "### v0.5.10 個別銘柄の補助情報・外部評価",
        "### v0.5.8 個別銘柄画面",
        "### v0.5.6 市場比較データの自動フォールバック",
        "### v0.5.3 画面操作・配当表示改善",
        "### v0.5.0 高速化とSBI CSV連携",
        "### v0.4.0 条件設定・説明性の強化",
        "### v0.3.4 TOPIX欠損時の安全性改善",
        "### v0.3.3 J-Quants契約期間対応",
        "### v0.3.2 J-Quantsレート制限制御",
    ]
    headings = [line for line in lines if line.startswith("### v")]
    assert headings == versions
    assert readme.index("## 開発履歴（新しい順）") < readme.index("## Windows / WSL での利用")
''',
    encoding="utf-8",
)

# Update old source-shape tests so they protect the same behavior through the
# new fragment wrapper instead of requiring the v0.6.52 direct-call layout.
history_path = Path("tests/test_history_dashboard.py")
history = history_path.read_text(encoding="utf-8")
replacements = {
    "    assert 'default_size=50, compact_sizes=True' in text\n": (
        "    assert 'default_size: int = 50' in text\n"
        "    assert 'compact_sizes: bool = True' in text\n"
    ),
    "    assert '_render_history_stock_buttons(page, \"daily_history\")' in text\n"
    "    assert '_render_history_stock_buttons(evaluation_page, \"evaluation_history\")' in text\n"
    "    assert '_render_history_stock_buttons(summary_page, \"star_summary\")' in text\n"
    "    assert '_render_history_stock_buttons(event_page, \"star_events_detail\")' in text\n": (
        "    assert '_render_history_stock_buttons(page, key)' in text\n"
        "    assert '_render_history_sortable_stock_table(sorted_hist, \"daily_history\")' in text\n"
        "    assert '_render_history_sortable_stock_table(sorted_e, \"evaluation_history\")' in text\n"
        "    assert '_render_history_sortable_stock_table(summary, \"star_summary\")' in text\n"
        "    assert '_render_history_sortable_stock_table(event_show, \"star_events_detail\")' in text\n"
    ),
    "    assert '_history_page_slice(sorted_hist, \"daily_history\", default_size=50, compact_sizes=True)' in text\n"
    "    assert '_history_page_slice(sorted_e, \"evaluation_history\", default_size=50, compact_sizes=True)' in text\n": (
        "    assert 'def _render_history_sortable_stock_table(' in text\n"
        "    assert 'default_size: int = 50' in text\n"
        "    assert 'compact_sizes: bool = True' in text\n"
        "    assert 'page = _history_page_slice(' in text\n"
        "    assert 'default_size=default_size' in text\n"
        "    assert 'compact_sizes=compact_sizes' in text\n"
    ),
}
for old, new in replacements.items():
    if old not in history:
        raise SystemExit(f"history dashboard test anchor not found: {old.splitlines()[0]}")
    history = history.replace(old, new, 1)
history_path.write_text(history, encoding="utf-8")

# Keep the original v0.6.52 sorting coverage, but verify the generic fragment
# sorts before pagination instead of requiring four duplicated direct calls.
Path("tests/test_sortable_clickable_tables.py").write_text(
    '''from pathlib import Path


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
    assert 'button(display_code' in text
    assert 'button(name or display_code' in text
    assert '_open_stock_detail(code)' in text
''',
    encoding="utf-8",
)
