from pathlib import Path


def test_market_regime_walk_forward_graph_shows_means_effect_interval_and_counts():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    start = text.index("def _render_market_regime_walk_forward_chart(")
    end = text.index("@st.cache_resource", start)
    renderer = text[start:end]

    assert "st.selectbox(" in renderer
    assert "go.Bar(" in renderer
    assert "go.Scatter(" in renderer
    assert "error_y={" in renderer
    assert '"選択効果95%区間下限"' in renderer
    assert '"選択効果95%区間上限"' in renderer
    assert '"確定エピソード数"' in renderer
    assert "少ない環境" in renderer
    assert "st.plotly_chart(" in renderer


def test_market_regime_walk_forward_graph_is_used_with_existing_summary():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "_render_market_regime_walk_forward_chart(regime_display)" in text
