from pathlib import Path


def test_walk_forward_chart_groups_comparisons_and_does_not_stack_selection_edge():
    dashboard = Path("dashboard.py").read_text(encoding="utf-8")
    start = dashboard.index("def _render_walk_forward_comparison_chart(")
    end = dashboard.index("@st.cache_resource", start)
    block = dashboard[start:end]

    assert 'barmode="group"' in block
    assert 'go.Bar(' in block
    assert 'go.Scatter(' in block
    assert 'marker={"symbol": "diamond"' in block
    assert 'fig.add_hline(y=0' in block
    assert 'st.bar_chart(display.set_index("期間")' not in dashboard
    assert "各系列は積み上げていません" in dashboard
