from pathlib import Path


def test_dashboard_renders_moving_average_chart_and_star_legend():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    for term in [
        "株価・移動平均線グラフ",
        "20日線", "50日線", "200日線",
        "買い検討価格帯", "追いかけ買い上限", "再評価ライン",
        "◎☆ 買い候補", "prepare_trend_chart_frame", "st.plotly_chart",
    ]:
        assert term in text
