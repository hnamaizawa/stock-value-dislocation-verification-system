from pathlib import Path


def test_benchmark_mode_is_defined_before_session_update():
    text = Path('dashboard.py').read_text(encoding='utf-8')
    definition = text.index('benchmark_mode = benchmark_options[benchmark_label]')
    usage = text.index('"ui_benchmark_mode": benchmark_mode')
    assert definition < usage


def test_benchmark_selector_is_in_condition_builder():
    text = Path('dashboard.py').read_text(encoding='utf-8')
    assert '"市場比較データ"' in text
    assert '"市場比較を使わない": "disabled"' in text
