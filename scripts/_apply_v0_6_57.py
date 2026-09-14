from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def replace_block(text: str, start_marker: str, end_marker: str, replacement: str, *, label: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    if start < 0 or end <= start:
        raise RuntimeError(f"{label}: invalid block bounds")
    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]


# dashboard.py -----------------------------------------------------------------
dashboard_path = "dashboard.py"
dashboard = read(dashboard_path)
dashboard = replace_once(
    dashboard,
    "def _history_stock_detail_url(code: str) -> str:\n    \"\"\"Build an absolute stock-detail URL for a separate browser tab.\"\"\"",
    "def _stock_detail_new_tab_url(code: str) -> str:\n    \"\"\"Build an absolute stock-detail URL for a separate browser tab.\"\"\"",
    label="rename new-tab URL helper",
)
dashboard = dashboard.replace("_history_stock_detail_url(code)", "_stock_detail_new_tab_url(code)")

candidate_block = '''@st.fragment
def _render_clickable_candidates(shortlist: pd.DataFrame) -> None:
    """Render candidate code and company name as new-tab stock-detail links."""
    st.caption("銘柄コードまたは企業名をクリックすると、個別銘柄検索を新しいタブで開きます。元の候補一覧はそのまま残ります。列名をクリックすると昇順／降順を切り替えられます。")
    score_field = "strategy_score" if "strategy_score" in shortlist.columns else "quantitative_score"
    display_shortlist = _sorted_clickable_table_frame(shortlist, "clickable_candidates")
    header = st.columns([1, 3, 1, 1, 1])
    for col, (label, field) in zip(
        header,
        [("コード", "code"), ("企業名", "name"), ("市場", "market"), ("終値", "close"), ("スコア", score_field)],
    ):
        _sortable_header_button(col, label, field, "clickable_candidates")
    for _, row in display_shortlist.iterrows():
        code = str(row.get("code", ""))
        display_code = display_tse_code(code)
        name = str(row.get("name", ""))
        cols = st.columns([1, 3, 1, 1, 1])
        stock_url = _stock_detail_new_tab_url(code)
        cols[0].link_button(
            display_code,
            stock_url,
            width="stretch",
            help="個別銘柄検索を新しいブラウザタブで開きます。",
        )
        cols[1].link_button(
            name or display_code,
            stock_url,
            width="stretch",
            help="個別銘柄検索を新しいブラウザタブで開きます。",
        )
        cols[2].write(str(row.get("market", "-")))
        cols[3].write(f"¥{_format_number(row.get('close'))}")
        cols[4].write(_format_number(row.get("strategy_score", row.get("quantitative_score")), 1))
'''
dashboard = replace_block(
    dashboard,
    "@st.fragment\ndef _render_clickable_candidates(shortlist: pd.DataFrame) -> None:",
    "@st.fragment\ndef _render_unified_candidate_table(result: pd.DataFrame, *, active_mode: bool) -> None:",
    candidate_block,
    label="candidate shortlist renderer",
)

unified_block = '''@st.fragment
def _render_unified_candidate_table(result: pd.DataFrame, *, active_mode: bool) -> None:
    """Render the sortable unified-candidate table without rerunning Yahoo analysis."""
    display_result = _sorted_clickable_table_frame(result, "unified_candidates")
    header = st.columns([1.15, 1.0, 2.4, 0.8, 1.0, 1.0, 1.6, 1.6, 1.35])
    unified_headers = [
        ("評価", "直感判定"), ("コード", "コード"), ("企業名", "企業名"),
        ("スコア", "定量スコア"), ("分析終値", "分析終値"), ("最新株価", "最新株価"),
        ("最新判定", "最新判定"), ("変化", "変化"), ("仮説警告", "仮説警告"),
    ]
    for col, (label, field) in zip(header, unified_headers):
        _sortable_header_button(col, label, field, "unified_candidates")
    for _, item in display_result.iterrows():
        cols = st.columns([1.15, 1.0, 2.4, 0.8, 1.0, 1.0, 1.6, 1.6, 1.35])
        cols[0].write(str(item["直感判定"]))
        raw_code = str(item["raw_code"])
        stock_url = _stock_detail_new_tab_url(raw_code)
        cols[1].link_button(
            str(item["コード"]),
            stock_url,
            width="stretch",
            help="個別銘柄検索を新しいブラウザタブで開きます。",
        )
        cols[2].link_button(
            str(item["企業名"]) or str(item["コード"]),
            stock_url,
            width="stretch",
            help="個別銘柄検索を新しいブラウザタブで開きます。",
        )
        cols[3].write(_format_number(item.get("定量スコア"), 1))
        cols[4].write(f"¥{_format_number(item.get('分析終値'))}")
        cols[5].write("-" if pd.isna(item.get("最新株価")) else f"¥{_format_number(item.get('最新株価'), 1)}")
        cols[6].write(str(item["最新判定"]))
        cols[7].write(str(item["変化"]))
        cols[8].write(str(item["仮説警告"]))
        with st.expander(f"詳細: {item['コード']} {item['企業名']}", expanded=False):
            detail_cols = st.columns(4)
            detail_cols[0].metric("約3カ月前", str(item["約3カ月前"]))
            detail_cols[1].metric("下降脱出", str(item["下降脱出"]))
            if active_mode:
                detail_cols[2].metric("最新60日ボラ", "-" if pd.isna(item.get("最新60日ボラ")) else f"{float(item['最新60日ボラ']):.1f}%")
                detail_cols[3].metric("最新20日値幅", "-" if pd.isna(item.get("最新20日値幅")) else f"{float(item['最新20日値幅']):.1f}%")
            st.caption(str(item["判断メモ"]))
    st.caption("Yahoo Finance系の最新情報は候補抽出スコア自体には混入しません。SBI証券の現在値・板・最新開示で最終確認してください。")
'''
dashboard = replace_block(
    dashboard,
    "@st.fragment\ndef _render_unified_candidate_table(result: pd.DataFrame, *, active_mode: bool) -> None:",
    "def _render_latest_candidate_trends(score_passed: pd.DataFrame, *, star_only: bool = False, analysis_as_of=None) -> pd.DataFrame:",
    unified_block,
    label="unified candidate renderer",
)
dashboard = replace_once(
    dashboard,
    "外部データ取得に失敗しても銘柄は消さず『判定不能』として残します。銘柄コードまたは企業名をクリックすると個別画面へ移動します。",
    "外部データ取得に失敗しても銘柄は消さず『判定不能』として残します。銘柄コードまたは企業名をクリックすると個別銘柄検索を新しいタブで開きます。元の候補一覧はそのまま残ります。",
    label="unified candidate caption",
)
write(dashboard_path, dashboard)


# Version metadata / docs -------------------------------------------------------
pyproject = read("pyproject.toml")
pyproject = replace_once(pyproject, 'version = "0.6.56"', 'version = "0.6.57"', label="pyproject version")
write("pyproject.toml", pyproject)

init = read("src/value_dislocation/__init__.py")
init = replace_once(init, '__version__ = "0.6.56"', '__version__ = "0.6.57"', label="package version")
write("src/value_dislocation/__init__.py", init)

readme = read("README.md")
readme = replace_once(readme, "Version: **0.6.56**", "Version: **0.6.57**", label="README version")
readme_entry = '''### v0.6.57 条件設定・候補から個別銘柄を新しいタブで確認

- 「条件設定・候補」の候補一覧と「統合候補一覧（抽出条件 + 最新トレンド）」で、銘柄コード／企業名をクリックすると個別銘柄検索を新しいブラウザタブで開くようにしました。
- 元の候補一覧・条件・ソート状態を残したまま複数銘柄を確認し、確認後は新しいタブを閉じるだけで一覧作業へ戻れます。
- v0.6.56 の履歴・実績検証と同じURLクエリ方式を共通利用し、新しいStreamlitセッションへ対象銘柄コードを引き渡します。
- 抽出条件、Yahoo/J-Quantsデータ取得、外的要因レビュー、安全境界は変更していません。

'''
readme = replace_once(
    readme,
    "### v0.6.56 履歴一覧から個別銘柄を新しいタブで確認\n",
    readme_entry + "### v0.6.56 履歴一覧から個別銘柄を新しいタブで確認\n",
    label="README history entry",
)
write("README.md", readme)

changelog = read("CHANGELOG.md")
changelog_entry = '''## v0.6.57
- 「条件設定・候補」の候補一覧と統合候補一覧で、銘柄コード／企業名を新しいブラウザタブで開くよう変更。
- v0.6.56 で導入したURLクエリ方式を共通化し、新しいStreamlitセッションで対象銘柄を個別銘柄検索へ自動設定。
- 元の候補一覧、条件、ソート状態を維持し、個別確認後は新しいタブを閉じるだけで一覧作業へ戻れるようにした。
- 抽出ロジック、データ取得、外的要因レビュー、SBI安全境界は変更なし。

'''
if not changelog.startswith("## v0.6.56\n"):
    raise RuntimeError("CHANGELOG top version is not v0.6.56")
changelog = changelog_entry + changelog
write("CHANGELOG.md", changelog)

tasks = read("tasks/CURRENT.md")
task_entry = '''## v0.6.57 candidate stock detail new tab

- [x] 条件設定・候補の候補一覧で銘柄コード／企業名を新しいブラウザタブで開く。
- [x] 統合候補一覧（抽出条件 + 最新トレンド）でも同じ新タブ動作に統一する。
- [x] 元の候補一覧・条件・ソート状態を保持する。
- [x] v0.6.56 のURLクエリ方式を共通利用し、新しいStreamlitセッションで対象銘柄を自動表示する。
- [x] 回帰テストとHarness契約を追加する。

'''
if not tasks.startswith("## v0.6.56 history stock detail new tab\n"):
    raise RuntimeError("tasks/CURRENT.md unexpected top section")
tasks = task_entry + tasks
write("tasks/CURRENT.md", tasks)

blueprint = read("harness/app_blueprint.yaml")
blueprint = replace_once(blueprint, "blueprint_version: 0.6.56", "blueprint_version: 0.6.57", label="blueprint version")
blueprint = replace_once(
    blueprint,
    "- history_stock_detail_new_tab_navigation\n",
    "- history_stock_detail_new_tab_navigation\n- candidate_stock_detail_new_tab_navigation\n",
    label="blueprint candidate capability",
)
blueprint = replace_once(
    blueprint,
    "- history_stock_detail_must_open_new_tab_without_mutating_history_session\n",
    "- history_stock_detail_must_open_new_tab_without_mutating_history_session\n- candidate_stock_detail_must_open_new_tab_without_mutating_candidate_session\n",
    label="blueprint candidate invariant",
)
blueprint = replace_once(
    blueprint,
    "  history_stock_detail_opens_new_tab: true\n",
    "  history_stock_detail_opens_new_tab: true\n  candidate_stock_detail_opens_new_tab: true\n",
    label="blueprint candidate UI requirement",
)
write("harness/app_blueprint.yaml", blueprint)


# Tests ------------------------------------------------------------------------
package_test = read("tests/test_package_init.py")
package_test = replace_once(package_test, 'assert value_dislocation.__version__ == "0.6.56"', 'assert value_dislocation.__version__ == "0.6.57"', label="package test version")
write("tests/test_package_init.py", package_test)

readme_test = read("tests/test_sort_performance_and_readme_structure.py")
readme_test = replace_once(readme_test, 'assert lines[2] == "Version: **0.6.56**"', 'assert lines[2] == "Version: **0.6.57**"', label="README test version")
readme_test = replace_once(
    readme_test,
    '        "### v0.6.56 履歴一覧から個別銘柄を新しいタブで確認",\n',
    '        "### v0.6.57 条件設定・候補から個別銘柄を新しいタブで確認",\n        "### v0.6.56 履歴一覧から個別銘柄を新しいタブで確認",\n',
    label="README heading order test",
)
write("tests/test_sort_performance_and_readme_structure.py", readme_test)

history_test = read("tests/test_history_dashboard.py")
history_test = history_test.replace("_history_stock_detail_url(code)", "_stock_detail_new_tab_url(code)")
new_candidate_test = '''def test_candidate_lists_open_stock_search_in_new_tab_and_keep_candidate_context():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    candidate_start = text.index("def _render_clickable_candidates(")
    candidate_end = text.index("@st.fragment\ndef _render_unified_candidate_table(", candidate_start)
    candidate_block = text[candidate_start:candidate_end]
    unified_start = text.index("def _render_unified_candidate_table(")
    unified_end = text.index("def _render_latest_candidate_trends(", unified_start)
    unified_block = text[unified_start:unified_end]
    assert candidate_block.count('.link_button(') == 2
    assert '_stock_detail_new_tab_url(code)' in candidate_block
    assert '_open_stock_detail(code)' not in candidate_block
    assert unified_block.count('.link_button(') == 2
    assert '_stock_detail_new_tab_url(raw_code)' in unified_block
    assert '_open_stock_detail(' not in unified_block
    assert '元の候補一覧はそのまま残ります' in text
    assert 'st.context.url' in text
    assert 'st.query_params.get("code", "")' in text
'''
history_test = replace_block(
    history_test,
    "def test_candidate_lists_keep_existing_same_tab_navigation():",
    "def test_history_button_lists_keep_paging_compact_for_performance():",
    new_candidate_test,
    label="history dashboard candidate navigation test",
)
write("tests/test_history_dashboard.py", history_test)

sortable_test = read("tests/test_sortable_clickable_tables.py")
sortable_test = sortable_test.replace("_history_stock_detail_url(code)", "_stock_detail_new_tab_url(code)")
write("tests/test_sortable_clickable_tables.py", sortable_test)

navigation_test = read("tests/test_dashboard_navigation.py")
navigation_test = replace_once(
    navigation_test,
    '    assert "def _open_stock_detail" in text\n    assert "st.switch_page(STOCK_DETAIL_PAGE)" in text\n    assert "unified_candidate_code_" in text\n    assert "unified_candidate_name_" in text\n',
    '    assert "def _stock_detail_new_tab_url" in text\n    assert "st.context.url" in text\n    assert \'st.query_params.get("code", "")\' in text\n    assert "個別銘柄検索を新しいタブで開きます" in text\n',
    label="dashboard navigation test",
)
write("tests/test_dashboard_navigation.py", navigation_test)

candidate_new_tab_test = '''from pathlib import Path


def test_candidate_tables_use_new_tab_links_without_streamlit_widget_keys():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    candidate_start = text.index("def _render_clickable_candidates(")
    candidate_end = text.index("@st.fragment\\ndef _render_unified_candidate_table(", candidate_start)
    candidate_block = text[candidate_start:candidate_end]
    unified_start = text.index("def _render_unified_candidate_table(")
    unified_end = text.index("def _render_latest_candidate_trends(", unified_start)
    unified_block = text[unified_start:unified_end]

    assert candidate_block.count(".link_button(") == 2
    assert unified_block.count(".link_button(") == 2
    assert "key=f\\\"candidate_" not in candidate_block
    assert "key=f\\\"unified_candidate_" not in unified_block
    assert "_open_stock_detail(" not in candidate_block
    assert "_open_stock_detail(" not in unified_block
    assert "_stock_detail_new_tab_url(code)" in candidate_block
    assert "_stock_detail_new_tab_url(raw_code)" in unified_block


def test_history_and_candidates_share_the_same_url_query_contract():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "def _stock_detail_new_tab_url(code: str) -> str:" in text
    assert 'query = urlencode({"code": str(code).strip()})' in text
    assert 'st.query_params.get("code", "")' in text
    assert 'url_path=STOCK_DETAIL_URL_PATH' in text
    assert text.count("_stock_detail_new_tab_url(") >= 4
'''
write("tests/test_candidate_new_tab_navigation.py", candidate_new_tab_test)


# Harness ----------------------------------------------------------------------
harness = read("scripts/harness_check.py")
new_instant_check = '''def check_instant_preset_and_candidate_navigation(root: Path) -> CheckResult:
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    required = [
        'on_change=_on_preset_change',
        'def _stock_detail_new_tab_url',
        'st.context.url',
        'st.query_params.get("code", "")',
        'key="stock_query"',
        'st.navigation(',
        'position="top"',
        'key="detail_dividend_shares"',
        '1株当たり予想年間配当',
    ]
    missing = [token for token in required if token not in dashboard]
    forbidden = ['st.radio(']
    found_forbidden = [token for token in forbidden if token in dashboard]
    passed = not missing and not found_forbidden
    return CheckResult(
        "instant_preset_and_candidate_navigation",
        passed,
        "ok" if passed else "missing=" + ", ".join(missing) + " forbidden=" + ", ".join(found_forbidden),
    )
'''
harness = replace_block(
    harness,
    "def check_instant_preset_and_candidate_navigation(root: Path) -> CheckResult:",
    "def check_history_stock_new_tab_navigation(root: Path) -> CheckResult:",
    new_instant_check,
    label="harness instant/candidate check",
)

new_history_and_candidate_checks = '''def check_history_stock_new_tab_navigation(root: Path) -> CheckResult:
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    start = dashboard.index("def _render_history_stock_buttons(")
    end = dashboard.index("@st.fragment\\ndef _render_history_sortable_stock_table(", start)
    history_block = dashboard[start:end]
    required = [
        "def _stock_detail_new_tab_url", "st.context.url", "urlencode",
        "_stock_detail_new_tab_url(code)", ".link_button(",
        'st.query_params.get("code", "")', 'url_path=STOCK_DETAIL_URL_PATH', "新しいタブ",
    ]
    missing = [token for token in required if token not in dashboard]
    same_tab_history_call = "_open_stock_detail(code)" in history_block
    passed = not missing and not same_tab_history_call and history_block.count(".link_button(") == 2
    return CheckResult(
        "history_stock_new_tab_navigation", passed,
        json.dumps({
            "missing": missing,
            "same_tab_history_call": same_tab_history_call,
            "link_button_count": history_block.count(".link_button("),
        }, ensure_ascii=False),
    )


def check_candidate_stock_new_tab_navigation(root: Path) -> CheckResult:
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    candidate_start = dashboard.index("def _render_clickable_candidates(")
    candidate_end = dashboard.index("@st.fragment\\ndef _render_unified_candidate_table(", candidate_start)
    candidate_block = dashboard[candidate_start:candidate_end]
    unified_start = dashboard.index("def _render_unified_candidate_table(")
    unified_end = dashboard.index("def _render_latest_candidate_trends(", unified_start)
    unified_block = dashboard[unified_start:unified_end]
    required = [
        "_stock_detail_new_tab_url(code)",
        "_stock_detail_new_tab_url(raw_code)",
        "元の候補一覧はそのまま残ります",
    ]
    missing = [token for token in required if token not in dashboard]
    same_tab_calls = [
        token for token in ("_open_stock_detail(code)", '_open_stock_detail(str(item["raw_code"]))')
        if token in candidate_block or token in unified_block
    ]
    link_counts = {
        "candidate": candidate_block.count(".link_button("),
        "unified": unified_block.count(".link_button("),
    }
    passed = not missing and not same_tab_calls and link_counts == {"candidate": 2, "unified": 2}
    return CheckResult(
        "candidate_stock_new_tab_navigation", passed,
        json.dumps({
            "missing": missing,
            "same_tab_calls": same_tab_calls,
            "link_counts": link_counts,
        }, ensure_ascii=False),
    )
'''
harness = replace_block(
    harness,
    "def check_history_stock_new_tab_navigation(root: Path) -> CheckResult:",
    "def check_dividend_screening(root: Path) -> CheckResult:",
    new_history_and_candidate_checks,
    label="harness history/candidate new-tab checks",
)
harness = replace_once(
    harness,
    "        check_history_stock_new_tab_navigation(root),\n        check_dividend_screening(root),\n",
    "        check_history_stock_new_tab_navigation(root),\n        check_candidate_stock_new_tab_navigation(root),\n        check_dividend_screening(root),\n",
    label="harness run list",
)
write("scripts/harness_check.py", harness)

print("v0.6.57 candidate new-tab navigation patch applied")
