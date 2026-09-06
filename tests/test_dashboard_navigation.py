from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_preset_updates_widgets_immediately_and_top_navigation_is_wired():
    text = (ROOT / "dashboard.py").read_text(encoding="utf-8")
    assert "on_change=_on_preset_change" in text
    assert "def _open_stock_detail" in text
    assert "st.switch_page(STOCK_DETAIL_PAGE)" in text
    assert "unified_candidate_code_" in text
    assert "unified_candidate_name_" in text
    assert 'key="stock_query"' in text
    assert "st.navigation(" in text
    assert 'position="top"' in text
    assert "st.radio(" not in text


def test_individual_stock_view_contains_dividend_output():
    text = (ROOT / "dashboard.py").read_text(encoding="utf-8")
    required = [
        'st.markdown("#### 配当情報")',
        '"1株当たり予想年間配当"',
        '"予想配当利回り"',
        '"予想配当性向"',
        'key="detail_dividend_shares"',
        '"年間配当（税引前）"',
        '"課税口座の概算受取額"',
        '"NISAの概算受取額"',
    ]
    for token in required:
        assert token in text
