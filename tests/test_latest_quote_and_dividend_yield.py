from pathlib import Path

def test_dashboard_recalculates_missing_dividend_yield():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "float(dividend_per_share) / float(yield_price)" in text
    assert "予想配当利回りは" in text

def test_latest_quote_is_optional_and_clearly_separated():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "_latest_external_quote" in text
    assert "非公式・遅延の可能性" in text
    assert "J-Quantsの分析スナップショットには混入させず" in text

def test_reference_annotation_has_smaller_font():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert ".vd-metric-reference" in text
    assert "font-size: 0.72rem" in text
