from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from value_dislocation.config import load_config
from value_dislocation.strategy.rule_learning import (
    LEARNED_RULE_KEYS,
    active_rules_path,
    learning_state_path,
    refresh_rule_learning_state,
)


def _base_config(*, auto_apply: bool = True) -> dict:
    return {
        "paths": {"prices": "data/curated/latest/prices.csv"},
        "universe": {
            "allowed_markets": ["Prime", "Standard", "Growth"],
            "min_average_turnover_yen_20d": 50_000_000,
            "min_price_yen": 200,
            "exclude_negative_equity": True,
        },
        "screen": {
            "selection_strategy": "value_dislocation",
            "minimum_equity_ratio": 0.30,
            "minimum_operating_cf_positive_ratio_3y": 0.6667,
            "minimum_sales_cagr_3y": -0.05,
            "minimum_operating_margin": 0.0,
            "maximum_forecast_op_decline": -0.20,
            "minimum_drawdown_52w": -0.18,
            "minimum_relative_underperformance_6m": -0.08,
            "quantitative_min_score": 42,
        },
        "rule_learning": {
            "enabled": True,
            "auto_apply": auto_apply,
            "primary_horizon_days": 90,
            "minimum_mature_events": 40,
            "minimum_train_events": 20,
            "minimum_validation_events": 10,
            "train_fraction": 0.70,
            "minimum_event_gap_days": 30,
            "minimum_mean_return_improvement": 0.02,
            "minimum_positive_rate_improvement": 0.0,
            "minimum_candidate_retention": 0.35,
            "maximum_confirmation_mean_decline": 0.01,
            "cooldown_days": 0,
        },
        "risk": {},
        "backtest": {},
    }


def _write_synthetic_history(project_root: Path, *, count: int = 100) -> None:
    analysis_dir = project_root / "data" / "history" / "analysis"
    prices_dir = project_root / "data" / "curated" / "latest"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    prices_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    prices = []
    start = pd.Timestamp("2024-01-01")
    for i in range(count):
        code = f"{10000 + i}"
        day = start + pd.Timedelta(days=i * 2)
        good = i % 2 == 0
        drawdown = -0.25 if good else -0.19
        rows.append(
            {
                "analysis_date": day.date().isoformat(),
                "code": code,
                "name": f"C{i}",
                "market": "Prime",
                "selection_strategy": "value_dislocation",
                "selected_for_review": True,
                "quantitative_score": 60.0,
                "strategy_score": 60.0,
                "close": 100.0,
                "drawdown_52w": drawdown,
                "relative_return_6m": -0.12,
                "sales_cagr_3y": 0.04,
                "operating_margin": 0.10,
                "operating_cf_positive_ratio_3y": 1.0,
                "equity_ratio": 0.50,
                "forecast_op_growth": 0.05,
                "average_turnover_yen_20d": 100_000_000,
                "fail_reasons": "",
            }
        )
        prices.append({"date": day.date().isoformat(), "code": code, "close": 100.0})
        prices.append({"date": (day + pd.Timedelta(days=30)).date().isoformat(), "code": code, "close": 105.0 if good else 99.0})
        prices.append({"date": (day + pd.Timedelta(days=90)).date().isoformat(), "code": code, "close": 120.0 if good else 96.0})
        prices.append({"date": (day + pd.Timedelta(days=180)).date().isoformat(), "code": code, "close": 125.0 if good else 95.0})
    pd.DataFrame(rows).to_csv(
        analysis_dir / "2024-01-01.csv.gz", index=False, compression="gzip"
    )
    pd.DataFrame(prices).to_csv(prices_dir / "prices.csv", index=False)


def test_rule_learning_auto_applies_only_robust_out_of_sample_change(tmp_path: Path):
    _write_synthetic_history(tmp_path)
    config = _base_config(auto_apply=True)

    state = refresh_rule_learning_state(tmp_path, config, force=True)

    assert state["status"] == "auto_applied"
    assert state["mature_event_count"] >= 40
    active = json.loads(active_rules_path(tmp_path).read_text(encoding="utf-8"))
    assert "minimum_drawdown_52w" in active["screen"]
    assert float(active["screen"]["minimum_drawdown_52w"]) <= -0.21
    change = active["last_change"]
    assert change["validation"]["mean_improvement"] >= 0.02
    assert change["train"]["mean_improvement"] >= 0.01


def test_rule_learning_can_generate_proposal_without_applying(tmp_path: Path):
    _write_synthetic_history(tmp_path)
    config = _base_config(auto_apply=False)

    state = refresh_rule_learning_state(tmp_path, config, force=True)

    assert state["status"] == "proposal_ready"
    assert "best_proposal" in state
    assert not active_rules_path(tmp_path).exists()


def test_rule_learning_waits_for_enough_mature_history(tmp_path: Path):
    _write_synthetic_history(tmp_path, count=10)
    config = _base_config(auto_apply=True)

    state = refresh_rule_learning_state(tmp_path, config, force=True)

    assert state["status"] == "insufficient_history"
    assert state["mature_event_count"] < state["required_mature_events"]
    assert not active_rules_path(tmp_path).exists()


def test_load_config_applies_runtime_overlay_without_rewriting_yaml(tmp_path: Path):
    config = _base_config(auto_apply=True)
    config_path = tmp_path / "config" / "real_data.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    original = config_path.read_text(encoding="utf-8")

    active_path = active_rules_path(tmp_path)
    active_path.parent.mkdir(parents=True, exist_ok=True)
    active_path.write_text(
        json.dumps({"screen": {"minimum_drawdown_52w": -0.24}}, ensure_ascii=False),
        encoding="utf-8",
    )

    loaded = load_config(config_path)

    assert loaded["screen"]["minimum_drawdown_52w"] == -0.24
    assert loaded["rule_learning_runtime"]["active_screen_overrides"] == {
        "minimum_drawdown_52w": -0.24
    }
    assert config_path.read_text(encoding="utf-8") == original
    assert learning_state_path(tmp_path).exists()


def test_human_external_event_thresholds_are_never_auto_learned():
    assert "minimum_externality" not in LEARNED_RULE_KEYS
    assert "minimum_temporary_probability" not in LEARNED_RULE_KEYS
    assert "minimum_catalyst_probability" not in LEARNED_RULE_KEYS


def test_rule_learning_has_no_market_data_or_network_fetch_dependency():
    text = Path("src/value_dislocation/strategy/rule_learning.py").read_text(encoding="utf-8")
    forbidden = ["yfinance", "jquants", "requests", "httpx", "fetch_yahoo", "fetch_and_curate"]
    assert not [token for token in forbidden if token in text.lower()]
