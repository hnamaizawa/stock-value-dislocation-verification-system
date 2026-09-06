from pathlib import Path


def test_link_button_calls_are_compatible_with_pinned_streamlit():
    source = Path("dashboard.py").read_text(encoding="utf-8")
    assert 'st.link_button("記事を開く", url, key=' not in source
    assert 'st.link_button("記事を開く", url)' in source
