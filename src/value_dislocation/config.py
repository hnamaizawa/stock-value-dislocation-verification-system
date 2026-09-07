from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigError(RuntimeError):
    pass


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"設定ファイルが見つかりません: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    required = {"paths", "universe", "screen", "risk", "backtest"}
    missing = required - set(data)
    if missing:
        raise ConfigError(f"設定ファイルに不足があります: {sorted(missing)}")

    # Learned rules are a runtime overlay only. The source YAML remains the stable
    # baseline, so every automatic change is inspectable and reversible.
    if bool(data.get("rule_learning", {}).get("enabled", False)):
        from value_dislocation.strategy.rule_learning import refresh_and_apply_rule_learning

        data = refresh_and_apply_rule_learning(config_path, data)
    return data


def project_root_from_config(path: str | Path) -> Path:
    return Path(path).resolve().parent.parent


def resolve_path(config_path: str | Path, value: str) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    return project_root_from_config(config_path) / p