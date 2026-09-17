from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigError(RuntimeError):
    pass


def load_config(
    path: str | Path,
    *,
    refresh_rule_learning: bool = False,
) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"設定ファイルが見つかりません: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    required = {"paths", "universe", "screen", "risk", "backtest"}
    missing = required - set(data)
    if missing:
        raise ConfigError(f"設定ファイルに不足があります: {sorted(missing)}")

    # Normal UI/config reads only overlay the already-learned rules. Scanning all
    # point-in-time history and recomputing forward returns is intentionally reserved
    # for an explicit market-data refresh so Streamlit navigation remains cheap.
    if bool(data.get("rule_learning", {}).get("enabled", False)):
        from value_dislocation.strategy.rule_learning import (
            apply_active_rule_overrides,
            refresh_and_apply_rule_learning,
        )

        if refresh_rule_learning:
            data = refresh_and_apply_rule_learning(config_path, data)
        else:
            data = apply_active_rule_overrides(data, project_root_from_config(config_path))
    return data


def project_root_from_config(path: str | Path) -> Path:
    return Path(path).resolve().parent.parent


def resolve_path(config_path: str | Path, value: str) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    return project_root_from_config(config_path) / p
