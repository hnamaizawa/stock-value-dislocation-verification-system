from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


CACHE_SCHEMA_VERSION = "v1"


def walk_forward_cache_key(
    *,
    data_signature: str,
    config: dict[str, Any],
    settings: Any,
    horizons: Iterable[int],
    app_version: str,
) -> str:
    payload = {
        "schema": CACHE_SCHEMA_VERSION,
        "data_signature": str(data_signature),
        "config": config,
        "settings": {
            "max_snapshots": int(settings.max_snapshots),
            "spacing_trading_days": int(settings.spacing_trading_days),
            "controls_per_event": int(settings.controls_per_event),
            "minimum_history_trading_days": int(settings.minimum_history_trading_days),
        },
        "horizons": [int(value) for value in horizons],
        "app_version": str(app_version),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def result_cache_path(cache_dir: Path, cache_key: str) -> Path:
    return Path(cache_dir) / "results" / f"{cache_key}.parquet"


def load_walk_forward_result(cache_dir: Path, cache_key: str) -> pd.DataFrame | None:
    path = result_cache_path(cache_dir, cache_key)
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def save_walk_forward_result(cache_dir: Path, cache_key: str, events: pd.DataFrame) -> Path:
    path = result_cache_path(cache_dir, cache_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.parquet")
    events.to_parquet(temporary, index=False)
    temporary.replace(path)
    return path


def feature_cache_path(cache_dir: Path, data_signature: str, as_of: pd.Timestamp) -> Path:
    safe_signature = hashlib.sha256(str(data_signature).encode("utf-8")).hexdigest()[:20]
    day = pd.Timestamp(as_of).date().isoformat()
    return Path(cache_dir) / "features" / safe_signature / f"{day}.parquet"


def load_feature_cache(cache_dir: Path, data_signature: str, as_of: pd.Timestamp) -> pd.DataFrame | None:
    path = feature_cache_path(cache_dir, data_signature, as_of)
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def save_feature_cache(
    cache_dir: Path,
    data_signature: str,
    as_of: pd.Timestamp,
    prepared: pd.DataFrame,
) -> Path:
    path = feature_cache_path(cache_dir, data_signature, as_of)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.parquet")
    prepared.to_parquet(temporary, index=False)
    temporary.replace(path)
    return path
