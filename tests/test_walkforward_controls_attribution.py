from __future__ import annotations

import numpy as np
import pandas as pd

from value_dislocation import validation
from value_dislocation.strategy.attribution import add_external_shock_attribution
from value_dislocation.strategy.criteria import copy_with_screen_overrides
from value_dislocation.strategy.features import price_features
from value_dislocation.validation import (
    WalkForwardConfig,
    _forward_return,
    matched_controls,
    supported_walk_forward_horizons,
    walk_forward_cohort_summary,
    walk_forward_entry_timing_summary,
    walk_forward_external_attribution_comparison,
    walk_forward_history_diagnostics,
    walk_forward_summary,
    walk_forward_validation,
    walk_forward_readiness,
)


def test_walk_forward_attribution_uses_only_prices_available_on_replay_date():
    dates = pd.bdate_range("2025-01-06", periods=40)
    rows = []
    close_series = {
        "A": [100.0] * 34 + [80.0] + [10.0] * 5,
        "B": [100.0] * 34 + [85.0] + [10.0] * 5,
        "C": [100.0] * 34 + [90.0] + [10.0] * 5,
        "D": [100.0] * 34 + [90.0] + [10.0] * 5,
        "E": [100.0] * 34 + [90.0] + [10.0] * 5,
    }
    topix_series = [1000.0] * 34 + [900.0] + [1500.0] * 5
    for code, closes in close_series.items():
        for i, date in enumerate(dates):
            close = closes[i]
            topix = topix_series[i]
            rows.append({
                "code": code, "date": date, "close": close,
                "high": max(close, 100.0), "low": close * 0.99,
                "volume": 10_000, "topix_close": topix,
            })
    prices = pd.DataFrame(rows)
    as_of = dates[34]
    companies = pd.DataFrame([
        {"code": code, "name": code, "sector": "Tech", "market": "Prime"}
        for code in close_series
    ])
    financials = pd.DataFrame([
        {"code": code, "disclosure_date": dates[0]} for code in close_series
    ])

    point_companies, point_prices, _, _ = validation._point_in_time_inputs(
        companies, prices, financials, as_of
    )
    assert set(point_companies["code"]) == set(close_series)
    assert point_prices["date"].max().normalize() == as_of.normalize()

    features = price_features(point_prices, as_of).set_index("code")
    sector_median = features["return_6m"].median()
    features["sector_return_6m_median"] = sector_median
    features["sector_peer_count_6m"] = features["return_6m"].count()
    assert features["sector_peer_count_6m"].eq(5).all()
    features["benchmark_source"] = "official_topix"
    features["benchmark_return_6m"] = features["topix_return_6m"]
    past_attribution = add_external_shock_attribution(features.reset_index()).set_index("code")
    assert np.isclose(
        past_attribution.loc["A", "external_shock_attribution"],
        np.clip(-sector_median, 0, -features.loc["A", "return_6m"]) / -features.loc["A", "return_6m"],
    )

    # Changing all post-selection prices cannot change the point-in-time result.
    altered = prices.copy()
    future = altered["date"] > as_of
    altered.loc[future, "close"] = 1_000_000.0
    altered.loc[future, "topix_close"] = 1.0
    _, altered_point_prices, _, _ = validation._point_in_time_inputs(
        companies, altered, financials, as_of
    )
    altered_features = price_features(altered_point_prices, as_of).set_index("code")
    altered_features["sector_return_6m_median"] = altered_features["return_6m"].median()
    altered_features["sector_peer_count_6m"] = altered_features["return_6m"].count()
    assert altered_features["sector_peer_count_6m"].eq(5).all()
    altered_features["benchmark_source"] = "official_topix"
    altered_features["benchmark_return_6m"] = altered_features["topix_return_6m"]
    altered_attribution = add_external_shock_attribution(altered_features.reset_index()).set_index("code")
    assert np.isclose(
        altered_attribution.loc["A", "external_shock_attribution"],
        past_attribution.loc["A", "external_shock_attribution"],
    )


def test_walk_forward_comparison_runs_sixteen_screen_variants(monkeypatch):
    seen = []

    def fake_walk_forward(companies, prices, financials, config, **kwargs):
        screen = config["screen"]
        seen.append((screen["external_shock_attribution_method"], screen["minimum_external_shock_attribution"], screen["use_relative_underperformance_filter"], screen["minimum_relative_underperformance_6m"]))
        count = int(screen["minimum_external_shock_attribution"] * 10) + int(screen["use_relative_underperformance_filter"])
        return pd.DataFrame([{
            "return_10d": 0.10,
            "control_return_10d": 0.02,
            "selection_edge_10d": 0.08,
        }] * count)

    monkeypatch.setattr(validation, "walk_forward_validation", fake_walk_forward)
    result = walk_forward_external_attribution_comparison(
        pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
        {"universe": {}, "screen": {"minimum_relative_underperformance_6m": -0.12}},
        settings=WalkForwardConfig(), horizons=(10,),
    )
    assert len(result) == 16
    assert len(seen) == 16
    assert {variant[3] for variant in seen} == {-0.08}
    assert {variant[0] for variant in seen} == {"v1_legacy", "v2_sector_absolute"}
    assert result["選択効果"].dropna().eq(0.08).all()


def test_dislocation_score_walk_forward_comparison_runs_both_modes(monkeypatch):
    modes = []

    def fake_walk_forward(companies, prices, financials, config, **kwargs):
        modes.append(config["screen"]["dislocation_score_mode"])
        return pd.DataFrame(columns=["selection_date", "code", "return_10d", "selection_edge_10d"])

    monkeypatch.setattr(validation, "walk_forward_validation", fake_walk_forward)
    prices = pd.DataFrame({"date": pd.bdate_range("2025-01-01", periods=180)})
    result = validation.walk_forward_dislocation_score_comparison(
        pd.DataFrame(), prices, pd.DataFrame(), {"universe": {}, "screen": {}},
        settings=WalkForwardConfig(minimum_history_trading_days=60), horizons=(10,),
    )
    assert modes == ["legacy_depth", "external_explained"]
    assert len(result) == 2
    assert result["確定エピソード数"].eq(0).all()


def test_external_shock_attribution_decomposes_decline():
    frame = pd.DataFrame([
        {"return_6m": -0.25, "sector_return_6m_median": -0.19, "benchmark_return_6m": -0.07},
    ])
    frame["sector_peer_count_6m"] = 5
    out = add_external_shock_attribution(frame).iloc[0]
    assert out["market_return_component_6m"] == -0.07
    assert np.isclose(out["sector_incremental_component_6m"], -0.12)
    assert np.isclose(out["company_specific_component_6m"], -0.06)
    assert np.isclose(out["external_shock_attribution"], 0.76)
    assert np.isclose(out["external_shock_attribution_score"], 76.0)


def test_external_shock_attribution_does_not_invent_missing_benchmark():
    frame = pd.DataFrame([
        {"return_6m": -0.20, "sector_return_6m_median": -0.15, "benchmark_return_6m": np.nan},
    ])
    frame["sector_peer_count_6m"] = 5
    out = add_external_shock_attribution(frame, method="v1_legacy").iloc[0]
    assert pd.isna(out["external_shock_attribution"])
    assert not bool(out["external_shock_attribution_available"])


def test_v2_attribution_matches_four_sector_absolute_cases():
    frame = pd.DataFrame([
        {"benchmark_return_6m": 0.10, "sector_return_6m_median": 0.00, "return_6m": -0.10},
        {"benchmark_return_6m": 0.10, "sector_return_6m_median": -0.05, "return_6m": -0.10},
        {"benchmark_return_6m": -0.10, "sector_return_6m_median": -0.10, "return_6m": -0.10},
        {"benchmark_return_6m": 0.00, "sector_return_6m_median": 0.00, "return_6m": -0.10},
    ])
    frame["sector_peer_count_6m"] = 5
    out = add_external_shock_attribution(frame)
    assert out["external_shock_attribution"].tolist() == [0.0, 0.5, 1.0, 0.0]
    assert out["external_shock_attribution"].between(0.0, 1.0).all()
    legacy = add_external_shock_attribution(frame, method="v1_legacy")
    assert legacy["external_shock_attribution"].tolist() == [1.0, 1.0, 1.0, 0.0]


def test_v2_attribution_clamps_sector_move_to_stock_decline():
    frame = pd.DataFrame([
        {"return_6m": -0.10, "sector_return_6m_median": -0.50, "sector_peer_count_6m": 5},
        {"return_6m": -0.10, "sector_return_6m_median": 0.20, "sector_peer_count_6m": 5},
    ])
    out = add_external_shock_attribution(frame)
    assert out["external_shock_attribution"].tolist() == [1.0, 0.0]


def test_v2_attribution_is_unavailable_for_non_decline_or_insufficient_sector_data():
    frame = pd.DataFrame([
        {"return_6m": 0.0, "sector_return_6m_median": -0.1, "benchmark_return_6m": -0.1, "sector_peer_count_6m": 5},
        {"return_6m": 0.1, "sector_return_6m_median": -0.1, "benchmark_return_6m": 0.0, "sector_peer_count_6m": 5},
        {"return_6m": -0.1, "sector_return_6m_median": np.nan, "benchmark_return_6m": 0.0, "sector_peer_count_6m": 5},
        {"return_6m": -0.1, "sector_return_6m_median": -0.1, "benchmark_return_6m": 0.0, "sector_peer_count_6m": 4},
    ])
    out = add_external_shock_attribution(frame)
    assert out["external_shock_attribution"].isna().all()
    assert out["external_shock_attribution_unavailable_reason"].tolist() == [
        "6か月騰落が0以上", "6か月騰落が0以上", "業種データ不足", "業種データ不足",
    ]


def test_matched_controls_prefers_same_sector_non_selected():
    universe = pd.DataFrame([
        {"code": "A", "sector": "Tech", "market": "Prime", "selected_for_review": True, "market_cap": 100, "drawdown_52w": -0.2, "volatility_60d": 0.3, "per_vs_sector": 1.0, "pbr_vs_sector": 1.0},
        {"code": "B", "sector": "Tech", "market": "Prime", "selected_for_review": False, "market_cap": 105, "drawdown_52w": -0.21, "volatility_60d": 0.31, "per_vs_sector": 1.02, "pbr_vs_sector": 0.98},
        {"code": "C", "sector": "Tech", "market": "Prime", "selected_for_review": False, "market_cap": 95, "drawdown_52w": -0.19, "volatility_60d": 0.29, "per_vs_sector": 0.98, "pbr_vs_sector": 1.03},
        {"code": "D", "sector": "Tech", "market": "Prime", "selected_for_review": False, "market_cap": 110, "drawdown_52w": -0.22, "volatility_60d": 0.32, "per_vs_sector": 1.03, "pbr_vs_sector": 1.04},
        {"code": "E", "sector": "Retail", "market": "Prime", "selected_for_review": False, "market_cap": 101, "drawdown_52w": -0.20, "volatility_60d": 0.30, "per_vs_sector": 1.0, "pbr_vs_sector": 1.0},
    ])
    controls = matched_controls(universe, universe.iloc[0], count=3)
    assert set(controls["code"]) == {"B", "C", "D"}
    assert not controls["selected_for_review"].any()


def test_walk_forward_summary_reports_selection_edge():
    events = pd.DataFrame([
        {"return_30d": 0.10, "control_return_30d": 0.02, "selection_edge_30d": 0.08},
        {"return_30d": -0.02, "control_return_30d": -0.05, "selection_edge_30d": 0.03},
    ])
    row = walk_forward_summary(events, horizons=(30,)).iloc[0]
    assert row["確定件数"] == 2
    assert np.isclose(row["候補平均"], 0.04)
    assert np.isclose(row["類似非選択平均"], -0.015)
    assert np.isclose(row["選択効果"], 0.055)
    assert np.isclose(row["選択効果プラス率"], 1.0)


def test_walk_forward_bootstrap_interval_tightens_with_more_episodes():
    values = [0.04, -0.01, 0.03, 0.00]

    def summarize(repeats):
        rows = []
        for i, value in enumerate(values * repeats):
            rows.append({
                "episode_id": f"episode-{i}",
                "selection_date": pd.Timestamp("2024-01-01") + pd.Timedelta(i, unit="D"),
                "code": f"{i:04d}",
                "return_30d": value + 0.01,
                "control_return_30d": 0.01,
                "selection_edge_30d": value,
            })
        return walk_forward_summary(pd.DataFrame(rows), horizons=(30,)).iloc[0]

    small = summarize(2)
    large = summarize(30)
    small_width = small["選択効果95%区間上限"] - small["選択効果95%区間下限"]
    large_width = large["選択効果95%区間上限"] - large["選択効果95%区間下限"]
    assert large_width < small_width


def test_walk_forward_history_diagnostics_reports_short_replay_and_security_history():
    dates = pd.bdate_range("2024-01-02", periods=300)
    prices = pd.concat([
        pd.DataFrame({"date": dates, "code": "A"}),
        pd.DataFrame({"date": dates[-100:], "code": "B"}),
    ], ignore_index=True)
    settings = WalkForwardConfig(
        max_snapshots=3, spacing_trading_days=20,
        minimum_history_trading_days=252, entry_delay_trading_days=(0,),
    )

    result = walk_forward_history_diagnostics(prices, settings=settings, horizons=(10,))

    assert result["excluded_for_insufficient_history"] == 1
    assert result["usable_replay_dates"] == 2
    assert result["excluded_security_date_pairs"] == 2


def test_consecutive_replay_selections_are_one_episode(monkeypatch):
    dates = pd.bdate_range("2024-01-02", periods=300)
    prices = pd.DataFrame({
        "code": "A", "date": dates, "close": np.linspace(100, 130, len(dates)),
        "high": np.linspace(101, 131, len(dates)), "low": np.linspace(99, 129, len(dates)),
        "volume": 1000,
    })
    companies = pd.DataFrame([{"code": "A", "name": "A社", "sector": "Tech", "market": "Prime"}])
    financials = pd.DataFrame([{"code": "A", "disclosure_date": dates[0]}])

    def fake_prepare(c, p, f, as_of):
        return pd.DataFrame([{
            "code": "A", "name": "A社", "sector": "Tech", "market": "Prime", "close": p.iloc[-1]["close"],
        }])

    def fake_apply(prepared, config):
        out = prepared.copy()
        out["selected_for_review"] = True
        return out

    monkeypatch.setattr(validation, "prepare_quantitative_universe", fake_prepare)
    monkeypatch.setattr(validation, "apply_quantitative_criteria", fake_apply)
    monkeypatch.setattr(validation, "build_buy_readiness", lambda metrics, **kwargs: {"evidence_score": 90, "checks": [], "decision_level": "consider"})
    monkeypatch.setattr(validation, "build_intuitive_signal", lambda readiness, transition: {"symbol": "◎", "legacy_star": False, "reversal_star": False, "star_rule_version": "test"})

    events = walk_forward_validation(
        companies, prices, financials, {},
        settings=WalkForwardConfig(max_snapshots=2, spacing_trading_days=5, minimum_history_trading_days=252, entry_delay_trading_days=(0,)),
        horizons=(2,),
    )

    assert len(events) == 2
    assert events["episode_id"].nunique() == 1
    assert events["episode_start_date"].nunique() == 1
    assert events["episode_occurrence"].tolist() == [1, 2]
    summary = walk_forward_summary(events, horizons=(2,)).iloc[0]
    assert summary["確定エピソード数"] == 1
    assert summary["延べ確定件数"] == 2


def test_walk_forward_compares_nested_star_cohorts_with_robust_metrics():
    events = pd.DataFrame([
        {"return_30d": 0.10, "legacy_star_eligible": True, "reversal_star_eligible": True},
        {"return_30d": -0.06, "legacy_star_eligible": True, "reversal_star_eligible": False},
        {"return_30d": 0.02, "legacy_star_eligible": False, "reversal_star_eligible": False},
    ])
    result = walk_forward_cohort_summary(events, horizon_days=30).set_index("判定段階")
    assert result.loc["定量候補全体", "確定件数"] == 3
    assert result.loc["旧◎☆条件", "確定件数"] == 2
    assert result.loc["反転確認済み◎☆", "確定件数"] == 1
    assert np.isclose(result.loc["旧◎☆条件", "中央値"], 0.02)
    assert np.isclose(result.loc["旧◎☆条件", "5%以上下落率"], 0.5)


def test_walk_forward_entry_timing_uses_only_reversal_star_events():
    events = pd.DataFrame([
        {
            "reversal_star_eligible": True,
            "return_30d": 0.10,
            "return_30d_entry_delay_3d": 0.07,
            "return_30d_entry_delay_5d": -0.06,
        },
        {
            "reversal_star_eligible": False,
            "return_30d": -0.50,
            "return_30d_entry_delay_3d": -0.50,
            "return_30d_entry_delay_5d": -0.50,
        },
    ])
    result = walk_forward_entry_timing_summary(events, horizon_days=30).set_index("買付タイミング")
    assert np.isclose(result.loc["選定日終値", "平均リターン"], 0.10)
    assert np.isclose(result.loc["3取引日待機", "平均リターン"], 0.07)
    assert np.isclose(result.loc["5取引日待機", "5%以上下落率"], 1.0)


def test_walk_forward_caps_horizons_to_available_price_history():
    prices = pd.DataFrame({"date": pd.bdate_range("2025-01-06", periods=155)})
    supported = supported_walk_forward_horizons(
        prices, (10, 20, 30, 60, 90, 180), minimum_history_trading_days=60,
        entry_delay_trading_days=(3, 5),
    )
    assert supported == (10, 20, 30, 60, 90)


def test_walk_forward_horizon_support_boundary_and_empty_history():
    minimum = pd.DataFrame({"date": pd.bdate_range("2025-01-06", periods=76)})
    insufficient = pd.DataFrame({"date": pd.bdate_range("2025-01-06", periods=74)})
    assert supported_walk_forward_horizons(minimum, (10, 20), minimum_history_trading_days=60) == (10,)
    assert supported_walk_forward_horizons(insufficient, (10, 20), minimum_history_trading_days=60) == ()
    assert supported_walk_forward_horizons(pd.DataFrame(), (10,)) == ()


def test_walk_forward_readiness_reports_required_history_horizons_and_mode_gap():
    prices = pd.DataFrame({"date": pd.bdate_range("2024-01-02", periods=500)})
    result = walk_forward_readiness(
        prices,
        requested_horizons=(10, 30, 90, 180),
        max_snapshots=8,
        spacing_trading_days=20,
        minimum_history_trading_days=252,
        entry_delay_trading_days=(3, 5),
    )
    assert result["available_trading_days"] == 500
    assert result["maximum_supported_horizon"] == 243
    assert result["supported_horizons"] == (10, 30, 90, 180)
    assert result["usable_replay_dates"] == 4
    assert result["minimum_sessions_for_one_replay_date"] == 438
    assert result["minimum_sessions_for_selected_mode"] == 578
    assert result["additional_sessions_for_selected_mode"] == 78


def test_walk_forward_readiness_reports_no_supported_horizon_when_history_is_short():
    prices = pd.DataFrame({"date": pd.bdate_range("2025-01-02", periods=260)})
    result = walk_forward_readiness(
        prices,
        requested_horizons=(10, 30),
        max_snapshots=3,
        spacing_trading_days=40,
    )
    assert result["maximum_supported_horizon"] == 0
    assert result["supported_horizons"] == ()
    assert result["minimum_sessions_for_one_replay_date"] == 268
    assert result["additional_sessions_for_selected_mode"] == 88


def test_real_price_lookback_default_is_extended_in_both_real_configs():
    import yaml

    for path in ("config/real_data.yaml", "config/real_data.example.yaml"):
        with open(path, encoding="utf-8") as handle:
            config = yaml.safe_load(handle)
        assert config["runtime"]["price_lookback_days"] == 900


def test_walk_forward_reports_point_in_time_rejection_diagnostics(monkeypatch):
    dates = pd.bdate_range("2026-01-05", periods=15)
    prices = pd.DataFrame({"code": ["A"] * len(dates), "date": dates, "close": 100.0})
    financials = pd.DataFrame([{"code": "A", "disclosure_date": dates[0]}])
    companies = pd.DataFrame([{"code": "A", "name": "A社", "sector": "Tech", "market": "Prime"}])

    def fake_prepare(c, p, f, as_of):
        return pd.DataFrame([{
            "code": "A", "name": "A社", "sector": "Tech", "market": "Prime", "close": 100.0,
        }])

    def fake_apply(prepared, config):
        out = prepared.copy()
        out["selected_for_review"] = False
        out["fail_reasons"] = "営業黒字 / 自己資本比率"
        return out

    monkeypatch.setattr(validation, "prepare_quantitative_universe", fake_prepare)
    monkeypatch.setattr(validation, "apply_quantitative_criteria", fake_apply)
    diagnostics = []
    events = walk_forward_validation(
        companies, prices, financials, {},
        settings=WalkForwardConfig(
            max_snapshots=1, spacing_trading_days=1,
            controls_per_event=1, minimum_history_trading_days=1,
        ),
        horizons=(2,),
        diagnostics=diagnostics,
    )

    assert events.empty
    assert len(diagnostics) == 1
    assert diagnostics[0]["evaluated_rows"] == 1
    assert diagnostics[0]["selected_rows"] == 0
    assert diagnostics[0]["fail_reason_counts"] == {"営業黒字": 1, "自己資本比率": 1}


def test_applied_screen_overrides_replace_base_rules_for_walk_forward():
    base = {"universe": {"min_price_yen": 100}, "screen": {"quantitative_min_score": 42}}
    overrides = {
        "universe": {"min_price_yen": 0},
        "screen": {"quantitative_min_score": 0, "use_structural_deterioration_guard": False},
    }

    applied = copy_with_screen_overrides(base, overrides)

    assert applied["universe"]["min_price_yen"] == 0
    assert applied["screen"]["quantitative_min_score"] == 0
    assert applied["screen"]["use_structural_deterioration_guard"] is False
    assert base["screen"]["quantitative_min_score"] == 42


def test_matched_controls_backfills_same_market_after_sector_priority():
    universe = pd.DataFrame([
        {"code": "A", "sector": "Tech", "market": "Prime", "selected_for_review": True, "market_cap": 100, "drawdown_52w": -0.2, "volatility_60d": 0.3, "per_vs_sector": 1.0, "pbr_vs_sector": 1.0},
        {"code": "B", "sector": "Tech", "market": "Prime", "selected_for_review": False, "market_cap": 500, "drawdown_52w": -0.4, "volatility_60d": 0.5, "per_vs_sector": 1.5, "pbr_vs_sector": 1.5},
        {"code": "C", "sector": "Retail", "market": "Prime", "selected_for_review": False, "market_cap": 101, "drawdown_52w": -0.2, "volatility_60d": 0.3, "per_vs_sector": 1.0, "pbr_vs_sector": 1.0},
        {"code": "D", "sector": "Bank", "market": "Prime", "selected_for_review": False, "market_cap": 102, "drawdown_52w": -0.2, "volatility_60d": 0.3, "per_vs_sector": 1.0, "pbr_vs_sector": 1.0},
    ])
    controls = matched_controls(universe, universe.iloc[0], count=3)
    assert controls["code"].tolist()[0] == "B"
    assert set(controls["code"]) == {"B", "C", "D"}


def test_forward_return_uses_trading_sessions_not_calendar_days():
    dates = pd.to_datetime(["2026-01-09", "2026-01-12", "2026-01-13", "2026-01-14"])
    groups = {"A": pd.DataFrame({"date": dates, "close": [100.0, 101.0, 110.0, 120.0]})}
    result, actual_days = _forward_return(groups, "A", pd.Timestamp("2026-01-09"), 100.0, 2)
    assert np.isclose(result, 0.10)
    assert actual_days == 4


def test_walk_forward_filters_future_inputs_before_selection(monkeypatch):
    dates = pd.bdate_range("2026-01-05", periods=15)
    prices = pd.DataFrame({
        "code": ["A"] * len(dates),
        "date": dates,
        "close": np.linspace(100.0, 114.0, len(dates)),
    })
    financials = pd.DataFrame([
        {"code": "A", "disclosure_date": dates[0], "marker": "past"},
        {"code": "A", "disclosure_date": dates[-1], "marker": "future"},
    ])
    companies = pd.DataFrame([{"code": "A", "name": "A社", "sector": "Tech", "market": "Prime"}])
    observed = {}

    def fake_prepare(c, p, f, as_of):
        observed["as_of"] = pd.Timestamp(as_of)
        observed["max_price"] = p["date"].max()
        observed["max_disclosure"] = f["disclosure_date"].max()
        return pd.DataFrame([{
            "code": "A", "name": "A社", "sector": "Tech", "market": "Prime",
            "close": float(p.iloc[-1]["close"]), "return_6m": -0.1,
        }])

    def fake_apply(prepared, config):
        out = prepared.copy()
        out["selected_for_review"] = True
        return out

    def fake_readiness(metrics, **kwargs):
        observed["trend_latest_price"] = kwargs["trend"].get("latest_price")
        return {"evidence_score": 90, "checks": [], "decision_level": "consider"}

    def fake_signal(readiness, transition):
        observed["signal_current_price"] = transition["current"].get("latest_price")
        return {
            "symbol": "◎☆", "legacy_star": True, "reversal_star": True,
            "star_rule_version": "test",
        }

    monkeypatch.setattr(validation, "prepare_quantitative_universe", fake_prepare)
    monkeypatch.setattr(validation, "apply_quantitative_criteria", fake_apply)
    monkeypatch.setattr(validation, "build_buy_readiness", fake_readiness)
    monkeypatch.setattr(validation, "build_intuitive_signal", fake_signal)
    events = walk_forward_validation(
        companies, prices, financials, {},
        settings=WalkForwardConfig(
            max_snapshots=1, spacing_trading_days=1,
            controls_per_event=1, minimum_history_trading_days=1,
        ),
        horizons=(2,),
    )
    assert not events.empty
    assert observed["max_price"] <= observed["as_of"]
    assert observed["max_disclosure"] <= observed["as_of"]
    expected_latest = float(prices.loc[prices["date"] <= observed["as_of"], "close"].iloc[-1])
    assert observed["trend_latest_price"] == expected_latest
    assert observed["signal_current_price"] == expected_latest
    assert bool(events.iloc[0]["reversal_star_eligible"])
    assert events.iloc[0]["universe_source"].startswith("current_master_fallback")


def test_walk_forward_module_has_no_market_fetch_dependency():
    source = __import__("inspect").getsource(validation)
    assert "fetch_and_curate_jquants" not in source
    assert "yfinance" not in source
