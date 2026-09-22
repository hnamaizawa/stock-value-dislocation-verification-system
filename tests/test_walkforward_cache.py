from __future__ import annotations

import numpy as np
import pandas as pd

from value_dislocation import validation
from value_dislocation.validation import (
    WalkForwardConfig,
    _forward_return,
    _forward_return_indexed,
    _price_groups,
    _price_index,
    walk_forward_validation,
)
from value_dislocation.walkforward_cache import (
    load_walk_forward_result,
    save_walk_forward_result,
    walk_forward_cache_key,
)


def test_indexed_forward_return_matches_reference():
    prices = pd.DataFrame({
        "code": ["A"] * 5,
        "date": pd.to_datetime([
            "2026-01-09", "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15"
        ]),
        "close": [100.0, 101.0, 110.0, 120.0, 125.0],
    })
    expected = _forward_return(
        _price_groups(prices), "A", pd.Timestamp("2026-01-09"), 100.0, 3
    )
    actual = _forward_return_indexed(
        _price_index(prices), "A", pd.Timestamp("2026-01-09"), 100.0, 3
    )
    assert actual == expected


def test_result_cache_round_trip_and_key_invalidation(tmp_path):
    settings = WalkForwardConfig(max_snapshots=3, spacing_trading_days=40, controls_per_event=3)
    key = walk_forward_cache_key(
        data_signature="data-a",
        config={"screen": {"minimum_score": 4}},
        settings=settings,
        horizons=(10, 30, 90),
        app_version="0.6.65",
    )
    changed = walk_forward_cache_key(
        data_signature="data-b",
        config={"screen": {"minimum_score": 4}},
        settings=settings,
        horizons=(10, 30, 90),
        app_version="0.6.65",
    )
    assert key != changed
    events = pd.DataFrame([{"selection_date": "2026-01-09", "code": "A", "return_10d": 0.1}])
    save_walk_forward_result(tmp_path, key, events)
    loaded = load_walk_forward_result(tmp_path, key)
    pd.testing.assert_frame_equal(loaded, events)


def test_walk_forward_reuses_feature_cache_and_reports_progress(monkeypatch, tmp_path):
    dates = pd.bdate_range("2026-01-05", periods=15)
    prices = pd.DataFrame({
        "code": ["A"] * len(dates),
        "date": dates,
        "close": np.linspace(100.0, 114.0, len(dates)),
    })
    financials = pd.DataFrame([
        {"code": "A", "disclosure_date": dates[0], "marker": "past"},
    ])
    companies = pd.DataFrame([
        {"code": "A", "name": "A社", "sector": "Tech", "market": "Prime"},
    ])
    prepare_calls = []

    def fake_prepare(c, p, f, as_of):
        prepare_calls.append(pd.Timestamp(as_of))
        return pd.DataFrame([{
            "code": "A", "name": "A社", "sector": "Tech", "market": "Prime",
            "close": float(p.iloc[-1]["close"]), "return_6m": -0.1,
        }])

    def fake_apply(prepared, config):
        out = prepared.copy()
        out["selected_for_review"] = True
        return out

    monkeypatch.setattr(validation, "prepare_quantitative_universe", fake_prepare)
    monkeypatch.setattr(validation, "apply_quantitative_criteria", fake_apply)
    settings = WalkForwardConfig(
        max_snapshots=1,
        spacing_trading_days=1,
        controls_per_event=1,
        minimum_history_trading_days=1,
    )
    progress = []
    first = walk_forward_validation(
        companies, prices, financials, {},
        settings=settings,
        horizons=(2,),
        cache_dir=tmp_path,
        data_signature="same-data",
        progress=progress.append,
    )
    second = walk_forward_validation(
        companies, prices, financials, {},
        settings=settings,
        horizons=(2,),
        cache_dir=tmp_path,
        data_signature="same-data",
        progress=progress.append,
    )
    assert not first.empty
    pd.testing.assert_frame_equal(first, second)
    assert len(prepare_calls) == 1
    assert any(item["stage"] == "feature_cache" for item in progress)
    assert any(item["stage"] == "completed" for item in progress)
