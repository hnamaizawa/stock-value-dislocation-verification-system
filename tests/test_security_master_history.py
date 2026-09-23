from __future__ import annotations

import json

import pandas as pd

from value_dislocation import validation
from value_dislocation.data.security_master_history import (
    archive_security_master,
    backfill_security_master_history,
    load_security_master_history,
    select_security_master_as_of,
)
from value_dislocation.validation import WalkForwardConfig, walk_forward_validation


def _companies(codes: list[str], day: str) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "code": code,
            "name": f"{code}社",
            "sector": "Tech",
            "market": "Prime",
            "master_date": day,
        }
        for code in codes
    ])


def test_archive_load_and_select_master_on_or_before_replay_date(tmp_path):
    archive_security_master(
        tmp_path, _companies(["A", "OLD"], "2025-12-31"),
        snapshot_date="2025-12-31", run_id="old-run",
    )
    archive_security_master(
        tmp_path, _companies(["A", "NEW"], "2026-02-01"),
        snapshot_date="2026-02-01", run_id="new-run",
    )
    snapshots = load_security_master_history(tmp_path)
    selected = select_security_master_as_of(snapshots, "2026-01-15")
    assert selected is not None
    assert selected.as_of == pd.Timestamp("2025-12-31")
    assert set(selected.companies["code"]) == {"A", "OLD"}
    assert select_security_master_as_of(snapshots, "2025-01-01") is None


def test_backfill_recovers_only_certified_actual_curated_runs(tmp_path):
    run = tmp_path / "data/curated/runs/run-1"
    run.mkdir(parents=True)
    _companies(["A", "OLD"], "2025-12-31").to_csv(run / "companies.csv", index=False)
    (run / "manifest.json").write_text(json.dumps({
        "actual_data": True,
        "sample_data": False,
        "run_id": "run-1",
        "data_cutoff_at": "2025-12-31",
    }), encoding="utf-8")
    sample_run = tmp_path / "data/curated/runs/sample-run"
    sample_run.mkdir(parents=True)
    _companies(["SAMPLE"], "2025-12-30").to_csv(sample_run / "companies.csv", index=False)
    (sample_run / "manifest.json").write_text(json.dumps({
        "actual_data": True,
        "sample_data": True,
        "run_id": "sample-run",
        "data_cutoff_at": "2025-12-30",
    }), encoding="utf-8")
    uncertified_run = tmp_path / "data/curated/runs/uncertified-run"
    uncertified_run.mkdir(parents=True)
    _companies(["UNKNOWN"], "2025-12-29").to_csv(
        uncertified_run / "companies.csv", index=False
    )
    (uncertified_run / "manifest.json").write_text(json.dumps({
        "actual_data": False,
        "sample_data": False,
        "run_id": "uncertified-run",
        "data_cutoff_at": "2025-12-29",
    }), encoding="utf-8")
    created = backfill_security_master_history(tmp_path)
    assert len(created) == 1
    assert created[0].name == "2025-12-31.csv.gz"
    snapshots = load_security_master_history(tmp_path)
    assert [snapshot.as_of for snapshot in snapshots] == [pd.Timestamp("2025-12-31")]
    assert len(backfill_security_master_history(tmp_path)) == 0


def test_walk_forward_uses_historical_master_for_delisted_security(monkeypatch, tmp_path):
    dates = pd.bdate_range("2026-01-05", periods=15)
    prices = pd.concat([
        pd.DataFrame({"code": code, "date": dates, "close": range(100, 115)})
        for code in ["A", "OLD"]
    ], ignore_index=True)
    financials = pd.DataFrame([
        {"code": "A", "disclosure_date": dates[0]},
        {"code": "OLD", "disclosure_date": dates[0]},
    ])
    current = _companies(["A"], "2026-02-01")
    archive_security_master(
        tmp_path, _companies(["A", "OLD"], "2026-01-01"),
        snapshot_date="2026-01-01", run_id="historical",
    )
    observed_codes: list[set[str]] = []

    def fake_prepare(c, p, f, as_of):
        observed_codes.append(set(c["code"]))
        return pd.DataFrame([
            {"code": code, "name": f"{code}社", "sector": "Tech", "market": "Prime",
             "close": 103.0, "return_6m": -0.1}
            for code in c["code"]
        ])

    def fake_apply(prepared, config):
        out = prepared.copy()
        out["selected_for_review"] = True
        return out

    monkeypatch.setattr(validation, "prepare_quantitative_universe", fake_prepare)
    monkeypatch.setattr(validation, "apply_quantitative_criteria", fake_apply)
    events = walk_forward_validation(
        current, prices, financials, {},
        settings=WalkForwardConfig(
            max_snapshots=1, spacing_trading_days=1,
            controls_per_event=1, minimum_history_trading_days=1,
        ),
        horizons=(2,),
        historical_masters=load_security_master_history(tmp_path),
    )
    assert observed_codes == [{"A", "OLD"}]
    assert set(events["code"]) == {"A", "OLD"}
    assert events["historical_master_available"].all()
    assert events["master_snapshot_date"].eq("2026-01-01").all()
    assert events["missing_master_code_count"].eq(0).all()
