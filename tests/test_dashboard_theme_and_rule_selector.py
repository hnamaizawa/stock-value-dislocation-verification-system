from pathlib import Path


def test_dashboard_has_switchable_soft_pastel_theme_and_rule_selector():
    source = Path("dashboard.py").read_text(encoding="utf-8")
    assert '"標準", "やわらかパステル"' in source
    assert "linear-gradient" in source
    assert "外的要因で下落 × 経営良好" in source
    assert "値動き活発（デイトレ候補）" in source
    assert "minimum_volatility_60d" in source
    assert "minimum_average_intraday_range_20d" in source
    assert "minimum_daytrade_activity_score" in source
    assert "J-Quants APIにはアクセスしません" in source


def test_soft_pastel_theme_is_more_pastel_and_scoped_to_theme_branch():
    source = Path("dashboard.py").read_text(encoding="utf-8")
    # The pastel CSS must stay behind the theme guard so the standard theme is unaffected.
    guard = 'if theme != "やわらかパステル":\n        return'
    assert guard in source
    pastel_source = source[source.index(guard):]
    for token in (
        "#ffeaf3",
        "#f5edff",
        "#eaf8ff",
        "#ffe4ef",
        "#f3e7ff",
        "#e5f6ff",
        'data-testid="stTabs"',
        'data-testid="stMetric"',
        'data-testid="stDataFrame"',
    ):
        assert token in pastel_source
