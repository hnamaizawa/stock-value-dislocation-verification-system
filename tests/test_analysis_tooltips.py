from pathlib import Path


def test_all_analysis_tables_use_shared_column_tooltips():
    source = Path("dashboard.py").read_text(encoding="utf-8")
    assert "ANALYSIS_ITEM_HELP" in source
    assert "def _analysis_column_config" in source
    assert "def _analysis_dataframe" in source
    # The only direct Streamlit dataframe call must be inside the shared helper.
    assert source.count("st.dataframe(") == 1
    assert "st.column_config.Column(" in source
    assert "help=_analysis_help(str(column))" in source


def test_major_analysis_views_have_beginner_hover_help():
    source = Path("dashboard.py").read_text(encoding="utf-8")
    required = [
        'help=_analysis_help("定量スコア")',
        'help=_analysis_help("selected_for_review")',
        'help=_analysis_help("final_evaluation")',
        'help=_analysis_help("候補イベント")',
        'help=_analysis_help("会社マスター最低カバレッジ")',
        'help="簡易は短時間、標準は通常確認、詳細は多くの過去時点を使う検証です。"',
        'help="企業名の一部、読み方、4桁・5桁の証券コードで検索できます。複数候補は選択画面で確認します。"',
        'help="この銘柄へ投入してよいと自分で決めた最大金額です。買付推奨額ではありません。"',
    ]
    assert not [item for item in required if item not in source]


def test_sortable_table_headers_explain_meaning_and_sort_action():
    source = Path("dashboard.py").read_text(encoding="utf-8")
    assert '_analysis_help(field, _analysis_help(label))' in source
    assert "クリックで昇順／降順を切り替えます。" in source

