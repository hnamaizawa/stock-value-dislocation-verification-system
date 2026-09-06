from pathlib import Path


DASHBOARD = Path("dashboard.py")
text = DASHBOARD.read_text(encoding="utf-8")

helper_anchor = "def _render_history_stock_buttons(\n"
helper = '''def _sorted_clickable_table_frame(frame: pd.DataFrame, key: str) -> pd.DataFrame:
    """Sort a custom clickable table using state set by its header buttons."""
    if frame.empty:
        return frame.reset_index(drop=True)
    sort_column = st.session_state.get(f"{key}_sort_column")
    if not sort_column or sort_column not in frame.columns:
        return frame.reset_index(drop=True)
    ascending = bool(st.session_state.get(f"{key}_sort_ascending", True))
    work = frame.copy()
    series = work[sort_column]
    non_null = series.notna()
    numeric = pd.to_numeric(series, errors="coerce")
    if bool(non_null.any()) and bool(numeric.loc[non_null].notna().all()):
        sort_value = numeric
    else:
        sort_value = series.fillna("").astype(str).str.casefold()
    work["__ui_sort_missing__"] = series.isna()
    work["__ui_sort_value__"] = sort_value
    work = work.sort_values(
        ["__ui_sort_missing__", "__ui_sort_value__"],
        ascending=[True, ascending],
        kind="mergesort",
    )
    return work.drop(columns=["__ui_sort_missing__", "__ui_sort_value__"]).reset_index(drop=True)


def _sortable_header_button(container, label: str, field: str, key: str) -> None:
    """Render a table header that toggles ascending/descending sort."""
    column_state = f"{key}_sort_column"
    ascending_state = f"{key}_sort_ascending"
    active_field = st.session_state.get(column_state)
    active_ascending = bool(st.session_state.get(ascending_state, True))
    if active_field == field:
        marker = " ▲" if active_ascending else " ▼"
    else:
        marker = " ↕"
    if container.button(
        f"{label}{marker}",
        key=f"{key}_sort_header_{field}",
        width="stretch",
        help="クリックで昇順／降順を切り替えます。",
    ):
        if active_field == field:
            st.session_state[ascending_state] = not active_ascending
        else:
            st.session_state[column_state] = field
            st.session_state[ascending_state] = True
        st.rerun()


'''
if "def _sorted_clickable_table_frame(" not in text:
    if helper_anchor not in text:
        raise SystemExit("history button helper anchor not found")
    text = text.replace(helper_anchor, helper + helper_anchor, 1)

old = '''    if caption:
        st.caption("銘柄コードまたは企業名ボタンをクリックすると、個別銘柄検索へ移動します。")

    display_frame = frame.reset_index(drop=True)
'''
new = '''    if caption:
        st.caption("銘柄コードまたは企業名ボタンをクリックすると、個別銘柄検索へ移動します。列名をクリックすると昇順／降順を切り替えられます。")

    display_frame = frame.reset_index(drop=True)
'''
if old not in text:
    raise SystemExit("history caption block not found")
text = text.replace(old, new, 1)

old = '''    header = st.columns([1.1, 2.5] + [1.15] * len(meta_cols))
    header[0].markdown("**コード**")
    header[1].markdown("**企業名**")
    for col, name in zip(header[2:], meta_cols):
        col.markdown(f"**{name}**")
'''
new = '''    header = st.columns([1.1, 2.5] + [1.15] * len(meta_cols))
    _sortable_header_button(header[0], "コード", "code", key)
    _sortable_header_button(header[1], "企業名", "name", key)
    for col, name in zip(header[2:], meta_cols):
        _sortable_header_button(col, name, name, key)
'''
if old not in text:
    raise SystemExit("history header block not found")
text = text.replace(old, new, 1)

old = '''def _render_clickable_candidates(shortlist: pd.DataFrame) -> None:
    """Render candidate code and company name as navigation buttons."""
    st.caption("銘柄コードまたは企業名をクリックすると、個別銘柄検索へ移動します。")
    header = st.columns([1, 3, 1, 1, 1])
    header[0].markdown("**コード**")
    header[1].markdown("**企業名**")
    header[2].markdown("**市場**")
    header[3].markdown("**終値**")
    header[4].markdown("**スコア**")
    for idx, row in shortlist.reset_index(drop=True).iterrows():
'''
new = '''def _render_clickable_candidates(shortlist: pd.DataFrame) -> None:
    """Render candidate code and company name as navigation buttons."""
    st.caption("銘柄コードまたは企業名をクリックすると、個別銘柄検索へ移動します。列名をクリックすると昇順／降順を切り替えられます。")
    score_field = "strategy_score" if "strategy_score" in shortlist.columns else "quantitative_score"
    display_shortlist = _sorted_clickable_table_frame(shortlist, "clickable_candidates")
    header = st.columns([1, 3, 1, 1, 1])
    for col, (label, field) in zip(
        header,
        [("コード", "code"), ("企業名", "name"), ("市場", "market"), ("終値", "close"), ("スコア", score_field)],
    ):
        _sortable_header_button(col, label, field, "clickable_candidates")
    for idx, row in display_shortlist.iterrows():
'''
if old not in text:
    raise SystemExit("clickable candidate block not found")
text = text.replace(old, new, 1)

old = '''    header = st.columns([1.15, 1.0, 2.4, 0.8, 1.0, 1.0, 1.6, 1.6, 1.35])
    for col, label in zip(header, ["評価", "コード", "企業名", "スコア", "分析終値", "最新株価", "最新判定", "変化", "仮説警告"]):
        col.markdown(f"**{label}**")
    for idx, item in result.reset_index(drop=True).iterrows():
'''
new = '''    result = _sorted_clickable_table_frame(result, "unified_candidates")
    header = st.columns([1.15, 1.0, 2.4, 0.8, 1.0, 1.0, 1.6, 1.6, 1.35])
    unified_headers = [
        ("評価", "直感判定"), ("コード", "コード"), ("企業名", "企業名"),
        ("スコア", "定量スコア"), ("分析終値", "分析終値"), ("最新株価", "最新株価"),
        ("最新判定", "最新判定"), ("変化", "変化"), ("仮説警告", "仮説警告"),
    ]
    for col, (label, field) in zip(header, unified_headers):
        _sortable_header_button(col, label, field, "unified_candidates")
    for idx, item in result.iterrows():
'''
if old not in text:
    raise SystemExit("unified candidate header block not found")
text = text.replace(old, new, 1)

replacements = [
    (
        '    page = _history_page_slice(sorted_hist, "daily_history", default_size=50, compact_sizes=True)\n',
        '    sorted_hist = _sorted_clickable_table_frame(sorted_hist, "daily_history")\n    page = _history_page_slice(sorted_hist, "daily_history", default_size=50, compact_sizes=True)\n',
    ),
    (
        '    evaluation_page = _history_page_slice(sorted_e, "evaluation_history", default_size=50, compact_sizes=True)\n',
        '    sorted_e = _sorted_clickable_table_frame(sorted_e, "evaluation_history")\n    evaluation_page = _history_page_slice(sorted_e, "evaluation_history", default_size=50, compact_sizes=True)\n',
    ),
    (
        '    summary_page = _history_page_slice(summary, "star_summary", default_size=50, compact_sizes=True)\n',
        '    summary = _sorted_clickable_table_frame(summary, "star_summary")\n    summary_page = _history_page_slice(summary, "star_summary", default_size=50, compact_sizes=True)\n',
    ),
    (
        '        event_page = _history_page_slice(event_show, "star_events_detail", default_size=50, compact_sizes=True)\n',
        '        event_show = _sorted_clickable_table_frame(event_show, "star_events_detail")\n        event_page = _history_page_slice(event_show, "star_events_detail", default_size=50, compact_sizes=True)\n',
    ),
]
for before, after in replacements:
    if before not in text:
        raise SystemExit(f"history page sort anchor not found: {before.strip()}")
    text = text.replace(before, after, 1)

DASHBOARD.write_text(text, encoding="utf-8")

pyproject_path = Path("pyproject.toml")
pyproject = pyproject_path.read_text(encoding="utf-8")
if 'version = "0.6.51"' not in pyproject:
    raise SystemExit("expected pyproject version 0.6.51")
pyproject_path.write_text(pyproject.replace('version = "0.6.51"', 'version = "0.6.52"', 1), encoding="utf-8")

readme_path = Path("README.md")
readme = readme_path.read_text(encoding="utf-8")
readme_section = '''## v0.6.52 一覧表の列クリックソート復活

- 統合候補一覧などのボタン式一覧で、列名クリックによる昇順／降順ソートを復活しました。
- ソート中の列には ▲（昇順）／▼（降順）を表示し、未選択列には ↕ を表示します。
- 銘柄コード／企業名のクリックによる個別銘柄検索への遷移は維持します。
- 履歴・検証のボタン式一覧は、ページング前の全検索結果を対象にソートします。

'''
if not readme.startswith("## v0.6.52"):
    readme_path.write_text(readme_section + readme, encoding="utf-8")

changelog_path = Path("CHANGELOG.md")
changelog = changelog_path.read_text(encoding="utf-8")
changelog_section = '''## v0.6.52
- ボタン式一覧の列見出しをクリック可能にし、同じ列を押すたびに昇順／降順を切り替えるソート機能を復活。
- 統合候補一覧、候補ボタン一覧、履歴・検証の各銘柄一覧へ共通ソート操作を適用。
- 履歴一覧はページング前にソートし、検索結果全体の並び順へ反映。
- 銘柄コード／企業名ボタンによる個別銘柄遷移、分析ロジック、データ取得、安全境界は変更なし。

'''
if not changelog.startswith("## v0.6.52"):
    changelog_path.write_text(changelog_section + changelog, encoding="utf-8")

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
    assert text.index('_sorted_clickable_table_frame(sorted_hist, "daily_history")') < text.index('_history_page_slice(sorted_hist, "daily_history"')
    assert text.index('_sorted_clickable_table_frame(sorted_e, "evaluation_history")') < text.index('_history_page_slice(sorted_e, "evaluation_history"')
    assert text.index('_sorted_clickable_table_frame(summary, "star_summary")') < text.index('_history_page_slice(summary, "star_summary"')
    assert text.index('_sorted_clickable_table_frame(event_show, "star_events_detail")') < text.index('_history_page_slice(event_show, "star_events_detail"')
    assert '_sortable_header_button(header[0], "コード", "code", key)' in text
    assert '_sortable_header_button(header[1], "企業名", "name", key)' in text
    assert 'button(display_code' in text
    assert 'button(name or display_code' in text
    assert '_open_stock_detail(code)' in text
''',
    encoding="utf-8",
)
