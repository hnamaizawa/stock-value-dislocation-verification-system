import pandas as pd
from value_dislocation.decision import build_price_trend_snapshot


def test_uptrend_snapshot_detects_rising_market():
    prices = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=240, freq="B"),
        "close": [100 + i * 0.5 for i in range(240)],
        "volume": [1000 + (i % 10) * 10 for i in range(240)],
    })
    result = build_price_trend_snapshot(prices)
    assert result["trend_state"] in {"上昇トレンド", "上昇転換の兆候"}
    assert result["sma20"] > result["sma50"] > result["sma200"]


def test_downtrend_snapshot_warns_about_falling_knife():
    prices = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=240, freq="B"),
        "close": [300 - i * 0.8 for i in range(240)],
        "volume": [1000 for _ in range(240)],
    })
    result = build_price_trend_snapshot(prices)
    assert result["trend_state"] in {"下向きトレンド", "明確な下向きトレンド"}
    assert any("落ちるナイフ" in text or "下落" in text for text in result["warnings"])


def test_trend_transition_detects_escape_from_prior_downtrend():
    from value_dislocation.decision import build_trend_transition
    dates = pd.date_range("2025-01-01", periods=260, freq="B")
    falling = pd.Series([200 - i * 0.5 for i in range(150)])
    recovering = pd.Series([125 + i * 0.9 for i in range(110)])
    prices = pd.DataFrame({"date": dates, "close": pd.concat([falling, recovering], ignore_index=True), "volume": 1000})
    result = build_trend_transition(prices, lookback_days=90)
    assert result["current_score"] > result["previous_score"]
    assert result["transition_state"] in {
        "下降トレンド脱出の可能性",
        "下降トレンドから上昇転換を確認",
        "上昇基調が改善",
        "上昇トレンド",
    }


def test_trend_transition_emits_no_deprecation_warning():
    import warnings
    import numpy as np
    from value_dislocation.decision import build_trend_transition

    prices = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=260, freq="B"),
        "close": [200 - i * 0.2 if i < 130 else 174 + (i - 130) * 0.3 for i in range(260)],
        "volume": [1000 for _ in range(260)],
    })
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        result = build_trend_transition(prices, lookback_days=np.int64(90))
    assert result["transition_state"]


def test_prepare_trend_chart_frame_adds_moving_averages():
    from value_dislocation.decision import prepare_trend_chart_frame

    prices = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=220, freq="B"),
        "close": range(100, 320),
        "volume": [1000] * 220,
    })
    result = prepare_trend_chart_frame(prices)
    assert list(result.columns) == ["date", "close", "sma20", "sma50", "sma200"]
    assert result["sma20"].iloc[-1] > 0
    assert result["sma50"].iloc[-1] > 0
    assert result["sma200"].iloc[-1] > 0
