from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def prepend(path: str, prefix: str) -> None:
    target = ROOT / path
    target.write_text(prefix + target.read_text(encoding="utf-8"), encoding="utf-8")


replace_once("pyproject.toml", 'version = "0.6.55"', 'version = "0.6.56"')
replace_once("src/value_dislocation/__init__.py", '__version__ = "0.6.55"', '__version__ = "0.6.56"')
replace_once("harness/app_blueprint.yaml", "blueprint_version: 0.6.55", "blueprint_version: 0.6.56")
replace_once("harness/app_blueprint.yaml", "- automatic_quantitative_rule_improvement\nnon_negotiable_invariants:", "- automatic_quantitative_rule_improvement\n- history_stock_detail_new_tab_navigation\nnon_negotiable_invariants:")
replace_once("harness/app_blueprint.yaml", "- source_yaml_must_not_be_rewritten_by_rule_learning\nrequired_files:", "- source_yaml_must_not_be_rewritten_by_rule_learning\n- history_stock_detail_must_open_new_tab_without_mutating_history_session\nrequired_files:")
replace_once("harness/app_blueprint.yaml", "  navigation_uses_session_state: true\n", "  navigation_uses_session_state: true\n  history_stock_detail_opens_new_tab: true\n")

replace_once(
    "scripts/harness_check.py",
    "def check_dividend_screening(root: Path) -> CheckResult:\n",
    '''def check_history_stock_new_tab_navigation(root: Path) -> CheckResult:\n    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")\n    start = dashboard.index("def _render_history_stock_buttons(")\n    end = dashboard.index("@st.fragment\\ndef _render_history_sortable_stock_table(", start)\n    history_block = dashboard[start:end]\n    required = [\n        "def _history_stock_detail_url", "st.context.url", "urlencode",\n        "_history_stock_detail_url(code)", ".link_button(",\n        'st.query_params.get("code", "")', 'url_path=STOCK_DETAIL_URL_PATH', "新しいタブ",\n    ]\n    missing = [token for token in required if token not in dashboard]\n    same_tab_history_call = "_open_stock_detail(code)" in history_block\n    candidate_navigation_preserved = (\n        'def _render_clickable_candidates(' in dashboard\n        and '_open_stock_detail(code)' in dashboard\n        and 'st.switch_page(STOCK_DETAIL_PAGE)' in dashboard\n    )\n    passed = not missing and not same_tab_history_call and candidate_navigation_preserved\n    return CheckResult(\n        "history_stock_new_tab_navigation", passed,\n        json.dumps({\n            "missing": missing,\n            "same_tab_history_call": same_tab_history_call,\n            "candidate_navigation_preserved": candidate_navigation_preserved,\n        }, ensure_ascii=False),\n    )\n\n\ndef check_dividend_screening(root: Path) -> CheckResult:\n''',
)
replace_once(
    "scripts/harness_check.py",
    '        "saved_user_profiles_must_not_be_copied_into_generated_apps",\n',
    '        "saved_user_profiles_must_not_be_copied_into_generated_apps",\n        "history_stock_detail_must_open_new_tab_without_mutating_history_session",\n',
)
replace_once(
    "scripts/harness_check.py",
    "        check_instant_preset_and_candidate_navigation(root),\n        check_dividend_screening(root),",
    "        check_instant_preset_and_candidate_navigation(root),\n        check_history_stock_new_tab_navigation(root),\n        check_dividend_screening(root),",
)

replace_once("README.md", "Version: **0.6.55**", "Version: **0.6.56**")
replace_once(
    "README.md",
    "### v0.6.55 履歴画面の generic timedelta 警告修正\n",
    "### v0.6.56 履歴一覧から個別銘柄を新しいタブで確認\n\n- 「履歴・実績検証」の銘柄コード／企業名をクリックすると、元の履歴一覧を残したまま個別銘柄検索を新しいブラウザタブで開くようにしました。\n- 新しいタブは別Streamlitセッションになるため、銘柄コードをURLクエリで引き渡し、自動的に対象銘柄を表示します。\n- 条件設定・候補画面の既存の同一タブ遷移は変更していません。\n\n### v0.6.55 履歴画面の generic timedelta 警告修正\n",
)
prepend(
    "CHANGELOG.md",
    "## v0.6.56\n- 「履歴・実績検証」の日次分析履歴・評価履歴・◎☆銘柄サマリ・◎☆イベント詳細で、銘柄コード／企業名を新しいブラウザタブで開くよう変更。\n- `st.link_button` とURLクエリの銘柄コードを使い、新しいStreamlitセッションでも対象銘柄を個別銘柄検索へ自動設定。\n- 元の履歴タブの検索条件・ページ・ソート状態を維持し、個別確認後は新しいタブを閉じるだけで一覧作業へ戻れるようにした。\n- 条件設定・候補画面の既存の同一タブ遷移、分析ロジック、データ取得、安全境界は変更なし。\n\n",
)
prepend(
    "tasks/CURRENT.md",
    "## v0.6.56 history stock detail new tab\n\n- [x] 履歴・実績検証の銘柄コード／企業名を新しいブラウザタブで開く。\n- [x] 元の履歴タブの検索・ページ・ソート状態を保持する。\n- [x] URLクエリで銘柄コードを新しいStreamlitセッションへ引き渡し、自動表示する。\n- [x] 条件設定・候補画面の既存の同一タブ遷移を維持する。\n- [x] 回帰テストとHarness契約を追加する。\n\n",
)
print("metadata/harness/docs patch applied")
