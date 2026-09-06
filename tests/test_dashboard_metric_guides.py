from pathlib import Path


def test_stock_detail_has_beginner_reference_labels():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "GENERAL_METRIC_GUIDES" in text
    assert "同業中央値" in text
    assert '("営業利益率", "operating_margin"' in text
    assert '("自己資本比率", "equity_ratio"' in text
    assert '("予想配当利回り", "forecast_dividend_yield"' in text
    assert "取得済み銘柄が5社以上" in text


def test_reference_helper_falls_back_to_general_guide():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert '"operating_margin": "目安 10%"' in text
    assert '"equity_ratio": "目安 40%"' in text
    assert '"forecast_dividend_yield": "目安 3%"' in text
