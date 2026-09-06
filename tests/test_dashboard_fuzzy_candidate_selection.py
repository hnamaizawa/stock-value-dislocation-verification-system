from pathlib import Path


def test_dashboard_requires_user_choice_for_multiple_fuzzy_matches():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    required = [
        '@st.dialog("検索候補を選択"',
        'index=None',
        'Never silently use the first fuzzy match',
        'st.session_state["stock_search_candidates"]',
        '選択した銘柄を表示',
        '候補選択後に個別銘柄を表示します',
    ]
    assert all(token in text for token in required)
