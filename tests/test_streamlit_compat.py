from pathlib import Path


def test_dashboard_has_no_deprecated_use_container_width():
    source = Path('dashboard.py').read_text(encoding='utf-8')
    assert 'use_container_width=' not in source
    assert 'width="stretch"' in source


def test_streamlit_minimum_version_includes_security_fixes():
    pyproject = Path('pyproject.toml').read_text(encoding='utf-8')
    assert 'streamlit>=1.54,<2' in pyproject


def test_pyarrow_minimum_version_includes_security_fixes():
    pyproject = Path('pyproject.toml').read_text(encoding='utf-8')
    assert 'pyarrow>=23.0.1,<27' in pyproject


def test_pytest_minimum_version_includes_security_fixes():
    pyproject = Path('pyproject.toml').read_text(encoding='utf-8')
    assert 'pytest>=9.0.3,<10' in pyproject
