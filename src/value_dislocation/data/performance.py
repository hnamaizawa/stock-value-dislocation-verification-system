from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..strategy.criteria import prepare_quantitative_universe
from .snapshot import sha256_file

FEATURE_FILE = "security_features.parquet"
FEATURE_CSV = "security_features.csv"
FEATURE_META = "security_features_meta.json"


def build_feature_snapshot(
    companies: pd.DataFrame,
    prices: pd.DataFrame,
    financials: pd.DataFrame,
    as_of: pd.Timestamp,
    output_dir: Path,
    *,
    prepared: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Persist one row per security for fast interactive screening.

    A pipeline that already computed ``prepared`` can pass it here so the expensive
    price/financial aggregation is not repeated merely to write the snapshot.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    features = (
        prepared
        if prepared is not None
        else prepare_quantitative_universe(companies, prices, financials, as_of)
    )
    parquet_path = output_dir / FEATURE_FILE
    csv_path = output_dir / FEATURE_CSV
    features.to_parquet(parquet_path, index=False, compression="zstd")
    features.to_csv(csv_path, index=False, encoding="utf-8-sig")
    meta = {
        "as_of": pd.Timestamp(as_of).isoformat(),
        "rows": int(len(features)),
        "columns": list(features.columns),
        "parquet": {"path": parquet_path.name, "sha256": sha256_file(parquet_path)},
        "csv": {"path": csv_path.name, "sha256": sha256_file(csv_path)},
    }
    (output_dir / FEATURE_META).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def load_feature_snapshot(output_dir: Path) -> pd.DataFrame | None:
    parquet_path = output_dir / FEATURE_FILE
    csv_path = output_dir / FEATURE_CSV
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    if csv_path.exists():
        return pd.read_csv(csv_path, dtype={"code": str})
    return None
