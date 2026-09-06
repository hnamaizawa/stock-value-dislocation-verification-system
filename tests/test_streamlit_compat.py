from pathlib import Path


def test_dashboard_has_no_deprecated_use_container_width():
    source = Path('dashboard.py').read_text(encoding='utf-8')
    assert 'use_container_width=' not in source
    assert 'width="stretch"' in source


def test_streamlit_is_pinned_to_verified_version():
    pyproject = Path('pyproject.toml').read_text(encoding='utf-8')
    assert 'streamlit==1.53.0' in pyproject
