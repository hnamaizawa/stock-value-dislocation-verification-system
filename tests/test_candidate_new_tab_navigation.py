from pathlib import Path


def test_candidate_tables_use_new_tab_links_without_streamlit_widget_keys():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    candidate_start = text.index("def _render_clickable_candidates(")
    candidate_end = text.index("@st.fragment\ndef _render_unified_candidate_table(", candidate_start)
    candidate_block = text[candidate_start:candidate_end]
    unified_start = text.index("def _render_unified_candidate_table(")
    unified_end = text.index("def _render_latest_candidate_trends(", unified_start)
    unified_block = text[unified_start:unified_end]

    assert candidate_block.count(".link_button(") == 2
    assert unified_block.count(".link_button(") == 2
    assert "key=f\"candidate_" not in candidate_block
    assert "key=f\"unified_candidate_" not in unified_block
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
