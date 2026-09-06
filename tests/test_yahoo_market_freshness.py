import pandas as pd

from value_dislocation.data.latest_quote import assess_yahoo_history_freshness


def test_yahoo_history_is_current_market_freshness_source():
    history = pd.DataFrame({
        "date": pd.to_datetime(["2026-08-07", "2026-08-10"]),
        "close": [100.0, 101.0],
    })
    result = assess_yahoo_history_freshness(
        history, max_age_days=7, now=pd.Timestamp("2026-08-11 20:00", tz="Asia/Tokyo")
    )
    assert result["source"].startswith("Yahoo Finance")
    assert result["latest_market_date"] == "2026-08-10"
    assert result["age_days"] == 1
    assert result["fresh"] is True


def test_stale_or_missing_yahoo_history_blocks_freshness():
    stale = pd.DataFrame({
        "date": pd.to_datetime(["2026-07-31"]),
        "close": [100.0],
    })
    result = assess_yahoo_history_freshness(
        stale, max_age_days=7, now=pd.Timestamp("2026-08-11 20:00", tz="Asia/Tokyo")
    )
    assert result["fresh"] is False
    assert result["age_days"] == 11
    assert assess_yahoo_history_freshness(None, max_age_days=7)["fresh"] is False
