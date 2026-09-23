from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

HISTORICAL_MASTER_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class SecurityMasterSnapshot:
    as_of: pd.Timestamp
    companies: pd.DataFrame
    path: Path


def _snapshot_day(companies: pd.DataFrame, fallback) -> pd.Timestamp:
    if "master_date" in companies.columns:
        dates = pd.to_datetime(companies["master_date"], errors="coerce").dropna()
        if not dates.empty:
            return pd.Timestamp(dates.max()).tz_localize(None).normalize()
    return pd.Timestamp(fallback).tz_localize(None).normalize()


def archive_security_master(
    project_root: Path,
    companies: pd.DataFrame,
    *,
    snapshot_date,
    run_id: str,
) -> Path:
    """Persist one immutable, dated listed-security master for later replay."""
    day = _snapshot_day(companies, snapshot_date)
    folder = Path(project_root) / "data" / "history" / "security_master"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{day.date().isoformat()}.csv.gz"
    if path.exists():
        return path
    temporary = path.with_suffix(".tmp.csv.gz")
    frame = companies.copy()
    frame["security_master_snapshot_date"] = day.date().isoformat()
    frame["security_master_source_run_id"] = str(run_id)
    frame.to_csv(temporary, index=False, compression="gzip", encoding="utf-8")
    temporary.replace(path)
    metadata = {
        "schema_version": HISTORICAL_MASTER_SCHEMA_VERSION,
        "snapshot_date": day.date().isoformat(),
        "run_id": str(run_id),
        "rows": len(frame),
    }
    metadata_path = folder / f"{day.date().isoformat()}.json"
    metadata_temporary = metadata_path.with_suffix(".tmp.json")
    metadata_temporary.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    metadata_temporary.replace(metadata_path)
    return path


def backfill_security_master_history(project_root: Path) -> list[Path]:
    """Recover dated masters from existing certified curated runs without API access."""
    root = Path(project_root)
    created: list[Path] = []
    for companies_path in sorted((root / "data" / "curated" / "runs").glob("*/companies.csv")):
        manifest_path = companies_path.parent / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not manifest.get("actual_data") or manifest.get("sample_data"):
                continue
            companies = pd.read_csv(companies_path, dtype={"code": str})
            fallback = manifest.get("data_cutoff_at")
            if not fallback:
                continue
            day = _snapshot_day(companies, fallback)
            target = root / "data" / "history" / "security_master" / f"{day.date().isoformat()}.csv.gz"
            if target.exists():
                continue
            created.append(archive_security_master(
                root,
                companies,
                snapshot_date=day,
                run_id=str(manifest.get("run_id", companies_path.parent.name)),
            ))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return created


def load_security_master_history(project_root: Path) -> list[SecurityMasterSnapshot]:
    """Load valid dated masters in chronological order; corrupt files are ignored."""
    folder = Path(project_root) / "data" / "history" / "security_master"
    snapshots: list[SecurityMasterSnapshot] = []
    for path in sorted(folder.glob("????-??-??.csv.gz")) if folder.exists() else []:
        try:
            day = pd.Timestamp(path.name[:10]).normalize()
            companies = pd.read_csv(path, dtype={"code": str})
            if companies.empty or "code" not in companies.columns:
                continue
            snapshots.append(SecurityMasterSnapshot(day, companies, path))
        except (OSError, ValueError):
            continue
    return snapshots


def select_security_master_as_of(
    snapshots: list[SecurityMasterSnapshot],
    as_of,
) -> SecurityMasterSnapshot | None:
    """Return the newest master known on or before the replay date."""
    cutoff = pd.Timestamp(as_of).tz_localize(None).normalize()
    eligible = [snapshot for snapshot in snapshots if snapshot.as_of <= cutoff]
    return max(eligible, key=lambda snapshot: snapshot.as_of) if eligible else None
