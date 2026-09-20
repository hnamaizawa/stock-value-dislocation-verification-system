from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RuleSpec:
    config_key: str
    metric: str
    operator: str
    fail_label: str
    step: float
    lower: float
    upper: float
    missing_pass: bool = False
    decimals: int = 4


# Only quantitative screening thresholds are learnable. Human external-event review
# thresholds deliberately stay outside this list.
RULE_SPECS: tuple[RuleSpec, ...] = (
    RuleSpec("minimum_equity_ratio", "equity_ratio", ">=", "自己資本比率", 0.05, 0.15, 0.70),
    RuleSpec(
        "minimum_operating_cf_positive_ratio_3y",
        "operating_cf_positive_ratio_3y",
        ">=",
        "営業CF履歴",
        1 / 6,
        0.0,
        1.0,
    ),
    RuleSpec("minimum_sales_cagr_3y", "sales_cagr_3y", ">=", "売上傾向", 0.02, -0.15, 0.20, True),
    RuleSpec("minimum_operating_margin", "operating_margin", ">=", "営業利益率", 0.02, -0.05, 0.30),
    RuleSpec("maximum_forecast_op_decline", "forecast_op_growth", ">=", "会社予想", 0.05, -0.50, 0.30, True),
    RuleSpec("minimum_drawdown_52w", "drawdown_52w", "<=", "52週高値からの下落", 0.03, -0.50, -0.08),
    RuleSpec(
        "minimum_relative_underperformance_6m",
        "relative_return_6m",
        "<=",
        "市場比較相対下落",
        0.03,
        -0.35,
        0.0,
        True,
    ),
    RuleSpec("quantitative_min_score", "quantitative_score", ">=", "定量スコア", 3.0, 20.0, 85.0, False, 1),
)

LEARNED_RULE_KEYS = {spec.config_key for spec in RULE_SPECS}
HORIZONS = (30, 90, 180)


def _project_path(project_root: Path, configured: str | Path) -> Path:
    path = Path(configured)
    return path if path.is_absolute() else project_root / path


def _state_dir(project_root: Path) -> Path:
    return project_root / "data" / "history" / "rule_learning"


def active_rules_path(project_root: Path) -> Path:
    return _state_dir(project_root) / "active_rules.json"


def learning_state_path(project_root: Path) -> Path:
    return _state_dir(project_root) / "state.json"


def audit_log_path(project_root: Path) -> Path:
    return _state_dir(project_root) / "audit.jsonl"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _append_audit(project_root: Path, value: dict[str, Any]) -> None:
    path = audit_log_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(value, ensure_ascii=False) + "\n")


def load_active_rule_overrides(project_root: Path) -> dict[str, Any]:
    payload = _read_json(active_rules_path(project_root))
    screen = payload.get("screen", {}) if isinstance(payload, dict) else {}
    if not isinstance(screen, dict):
        return {}
    return {k: v for k, v in screen.items() if k in LEARNED_RULE_KEYS}


def clear_active_rule_overrides(project_root: Path) -> None:
    path = active_rules_path(project_root)
    if path.exists():
        path.unlink()
    _append_audit(
        project_root,
        {"at": _now_iso(), "action": "manual_clear", "screen": {}},
    )


def apply_active_rule_overrides(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    overrides = load_active_rule_overrides(project_root)
    if not overrides:
        return config
    copied = json.loads(json.dumps(config))
    screen = copied.setdefault("screen", {})
    for key, value in overrides.items():
        screen[key] = value
    copied.setdefault("rule_learning_runtime", {})["active_screen_overrides"] = overrides
    copied["rule_learning_runtime"]["active_rules_path"] = str(active_rules_path(project_root))
    return copied


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _history_signature(project_root: Path, prices_path: Path, config: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    analysis_dir = project_root / "data" / "history" / "analysis"
    for path in sorted(analysis_dir.glob("????-??-??.csv.gz")) if analysis_dir.exists() else []:
        stat = path.stat()
        digest.update(f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    if prices_path.exists():
        stat = prices_path.stat()
        digest.update(f"prices:{prices_path.name}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    screen = config.get("screen", {})
    baseline = {spec.config_key: screen.get(spec.config_key) for spec in RULE_SPECS}
    digest.update(json.dumps(baseline, sort_keys=True, default=str).encode())
    return digest.hexdigest()


def _load_analysis(project_root: Path) -> pd.DataFrame:
    folder = project_root / "data" / "history" / "analysis"
    frames: list[pd.DataFrame] = []
    if not folder.exists():
        return pd.DataFrame()
    for path in sorted(folder.glob("????-??-??.csv.gz")):
        try:
            frame = pd.read_csv(path, dtype={"code": str}, compression="gzip")
        except Exception:
            continue
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    out["code"] = out.get("code", pd.Series(dtype=str)).astype(str)
    out["analysis_date"] = pd.to_datetime(out.get("analysis_date"), errors="coerce")
    if "selection_strategy" in out.columns:
        out = out.loc[out["selection_strategy"].fillna("value_dislocation").astype(str) == "value_dislocation"].copy()
    return out.dropna(subset=["analysis_date", "code"])


def _load_prices(prices_path: Path) -> pd.DataFrame:
    candidates = [prices_path]
    if prices_path.suffix.lower() == ".csv":
        candidates.insert(0, prices_path.with_suffix(".parquet"))
    for path in candidates:
        if not path.exists():
            continue
        try:
            if path.suffix.lower() == ".parquet":
                frame = pd.read_parquet(path)
            else:
                frame = pd.read_csv(path, dtype={"code": str})
        except Exception:
            continue
        if {"date", "code", "close"}.issubset(frame.columns):
            frame = frame[["date", "code", "close"]].copy()
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
            frame["code"] = frame["code"].astype(str)
            frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
            return frame.dropna(subset=["date", "close"]).sort_values(["code", "date"])
    return pd.DataFrame()


def _attach_forward_returns(analysis: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    if analysis.empty or prices.empty:
        return pd.DataFrame()
    frame = analysis.copy()
    frame["close"] = pd.to_numeric(frame.get("close"), errors="coerce")

    # Build the price lookup once. The previous implementation filtered the complete
    # multi-million-row price DataFrame once per security, which becomes effectively
    # O(securities x price_rows) as history grows and can pin a CPU core for minutes.
    price_groups: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for code, px in prices.groupby("code", sort=False):
        ordered = px[["date", "close"]].sort_values("date")
        price_groups[str(code)] = (
            ordered["date"].to_numpy(dtype="datetime64[ns]"),
            ordered["close"].to_numpy(dtype=float),
        )

    result_parts: list[pd.DataFrame] = []
    for code, rows in frame.groupby("code", sort=False):
        price_arrays = price_groups.get(str(code))
        if price_arrays is None:
            continue
        dates, closes = price_arrays
        g = rows.sort_values("analysis_date").copy()
        entry = pd.to_numeric(g["close"], errors="coerce").to_numpy(dtype=float)
        base_dates = g["analysis_date"].to_numpy(dtype="datetime64[ns]")
        for horizon in HORIZONS:
            target = base_dates + np.timedelta64(horizon, "D")
            pos = np.searchsorted(dates, target, side="left")
            values = np.full(len(g), np.nan, dtype=float)
            valid = (pos < len(dates)) & np.isfinite(entry) & (entry > 0)
            if valid.any():
                values[valid] = closes[pos[valid]] / entry[valid] - 1.0
            g[f"return_{horizon}d"] = values
        result_parts.append(g)
    return pd.concat(result_parts, ignore_index=True, sort=False) if result_parts else pd.DataFrame()


def _deduplicate_overlapping_events(frame: pd.DataFrame, gap_days: int) -> pd.DataFrame:
    if frame.empty or gap_days <= 0:
        return frame
    kept: list[int] = []
    for _, group in frame.sort_values(["code", "analysis_date"]).groupby("code", sort=False):
        last: pd.Timestamp | None = None
        for idx, row in group.iterrows():
            day = pd.Timestamp(row["analysis_date"])
            if last is None or (day - last).days >= gap_days:
                kept.append(idx)
                last = day
    return frame.loc[kept].sort_values("analysis_date").reset_index(drop=True)


def _fail_reason_set(value: Any) -> set[str]:
    if pd.isna(value):
        return set()
    return {part.strip() for part in str(value).split("/") if part.strip()}


def _eligible_for_rule(frame: pd.DataFrame, spec: RuleSpec) -> pd.Series:
    selected = frame.get("selected_for_review", pd.Series(False, index=frame.index))
    if not isinstance(selected, pd.Series):
        selected = pd.Series(bool(selected), index=frame.index)
    if pd.api.types.is_bool_dtype(selected):
        selected_mask = selected.fillna(False).astype(bool)
    else:
        selected_mask = selected.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})
    failures = frame.get("fail_reasons", pd.Series("", index=frame.index)).apply(_fail_reason_set)
    near_miss = failures.apply(lambda reasons: bool(reasons) and reasons.issubset({spec.fail_label}))
    return selected_mask | near_miss


def _passes(values: pd.Series, spec: RuleSpec, threshold: float) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if spec.operator == ">=":
        passed = numeric >= threshold
    else:
        passed = numeric <= threshold
    if spec.missing_pass:
        passed = passed | numeric.isna()
    return passed.fillna(False)


def _metrics(frame: pd.DataFrame, horizon: int) -> dict[str, float | int | None]:
    values = pd.to_numeric(frame.get(f"return_{horizon}d", pd.Series(index=frame.index, dtype=float)), errors="coerce").dropna()
    if values.empty:
        return {"count": 0, "mean": None, "median": None, "positive_rate": None}
    return {
        "count": int(len(values)),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "positive_rate": float((values > 0).mean()),
    }


def _candidate_values(spec: RuleSpec, current: float) -> list[float]:
    values = [current - 2 * spec.step, current - spec.step, current, current + spec.step, current + 2 * spec.step]
    normalized = []
    for value in values:
        bounded = min(spec.upper, max(spec.lower, value))
        rounded = round(bounded, spec.decimals)
        if rounded not in normalized:
            normalized.append(rounded)
    return normalized


def _evaluate_candidate(
    frame: pd.DataFrame,
    spec: RuleSpec,
    current: float,
    candidate: float,
    settings: dict[str, Any],
) -> dict[str, Any] | None:
    eligible = frame.loc[_eligible_for_rule(frame, spec)].copy()
    if eligible.empty or spec.metric not in eligible.columns:
        return None
    primary = int(settings.get("primary_horizon_days", 90))
    eligible = eligible.loc[pd.to_numeric(eligible.get(f"return_{primary}d", pd.Series(index=eligible.index, dtype=float)), errors="coerce").notna()].copy()
    if eligible.empty:
        return None

    unique_days = sorted(pd.to_datetime(eligible["analysis_date"], errors="coerce").dropna().unique())
    if len(unique_days) < 2:
        return None
    split_fraction = float(settings.get("train_fraction", 0.70))
    split_index = min(max(int(len(unique_days) * split_fraction), 1), len(unique_days) - 1)
    split_day = pd.Timestamp(unique_days[split_index])
    train = eligible.loc[eligible["analysis_date"] < split_day]
    valid = eligible.loc[eligible["analysis_date"] >= split_day]

    baseline_train = train.loc[_passes(train[spec.metric], spec, current)]
    candidate_train = train.loc[_passes(train[spec.metric], spec, candidate)]
    baseline_valid = valid.loc[_passes(valid[spec.metric], spec, current)]
    candidate_valid = valid.loc[_passes(valid[spec.metric], spec, candidate)]

    bt = _metrics(baseline_train, primary)
    ct = _metrics(candidate_train, primary)
    bv = _metrics(baseline_valid, primary)
    cv = _metrics(candidate_valid, primary)
    min_train = int(settings.get("minimum_train_events", 20))
    min_valid = int(settings.get("minimum_validation_events", 10))
    if min(bt["count"], ct["count"]) < min_train or min(bv["count"], cv["count"]) < min_valid:
        return None
    if any(x is None for x in (bt["mean"], ct["mean"], bv["mean"], cv["mean"], bv["positive_rate"], cv["positive_rate"])):
        return None

    retention = float(cv["count"]) / max(float(bv["count"]), 1.0)
    min_retention = float(settings.get("minimum_candidate_retention", 0.35))
    min_mean = float(settings.get("minimum_mean_return_improvement", 0.02))
    min_positive = float(settings.get("minimum_positive_rate_improvement", 0.00))
    train_improvement = float(ct["mean"]) - float(bt["mean"])
    valid_improvement = float(cv["mean"]) - float(bv["mean"])
    positive_improvement = float(cv["positive_rate"]) - float(bv["positive_rate"])

    confirmation_ok = True
    confirmations: dict[str, Any] = {}
    tolerated_decline = float(settings.get("maximum_confirmation_mean_decline", 0.01))
    for horizon in (30, 180):
        base = _metrics(baseline_valid, horizon)
        cand = _metrics(candidate_valid, horizon)
        confirmations[str(horizon)] = {"baseline": base, "candidate": cand}
        if min(base["count"], cand["count"]) >= max(5, min_valid // 2):
            if base["mean"] is not None and cand["mean"] is not None and float(cand["mean"]) < float(base["mean"]) - tolerated_decline:
                confirmation_ok = False

    accepted = (
        candidate != current
        and retention >= min_retention
        and train_improvement >= min_mean / 2
        and valid_improvement >= min_mean
        and positive_improvement >= min_positive
        and confirmation_ok
    )
    score = valid_improvement + 0.25 * positive_improvement + 0.15 * train_improvement
    return {
        "rule": spec.config_key,
        "metric": spec.metric,
        "fail_label": spec.fail_label,
        "current": current,
        "candidate": candidate,
        "accepted": accepted,
        "score": score,
        "retention": retention,
        "train": {"baseline": bt, "candidate": ct, "mean_improvement": train_improvement},
        "validation": {
            "baseline": bv,
            "candidate": cv,
            "mean_improvement": valid_improvement,
            "positive_rate_improvement": positive_improvement,
        },
        "confirmations": confirmations,
    }


def _cooldown_active(state: dict[str, Any], settings: dict[str, Any]) -> bool:
    last = state.get("last_applied_at")
    if not last:
        return False
    try:
        at = pd.Timestamp(last)
        if at.tzinfo is None:
            at = at.tz_localize("UTC")
        now = pd.Timestamp.now(tz="UTC")
        return (now - at).days < int(settings.get("cooldown_days", 30))
    except Exception:
        return False


def refresh_rule_learning_state(
    project_root: Path,
    config: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    settings = config.get("rule_learning", {})
    if not bool(settings.get("enabled", False)):
        return {"status": "disabled"}

    prices_value = config.get("paths", {}).get("prices", "")
    prices_path = _project_path(project_root, prices_value) if prices_value else Path()
    signature = _history_signature(project_root, prices_path, config)
    previous_state = _read_json(learning_state_path(project_root))
    active = load_active_rule_overrides(project_root)
    if not force and previous_state.get("source_signature") == signature:
        return previous_state

    state: dict[str, Any] = {
        "updated_at": _now_iso(),
        "source_signature": signature,
        "status": "evaluated",
        "auto_apply": bool(settings.get("auto_apply", True)),
        "active_screen_overrides": active,
        "primary_horizon_days": int(settings.get("primary_horizon_days", 90)),
    }
    if _cooldown_active(previous_state, settings):
        state.update({
            "status": "cooldown",
            "last_applied_at": previous_state.get("last_applied_at"),
            "last_applied_change": previous_state.get("last_applied_change"),
        })
        _write_json(learning_state_path(project_root), state)
        return state

    analysis = _load_analysis(project_root)
    prices = _load_prices(prices_path)
    enriched = _attach_forward_returns(analysis, prices)
    enriched = _deduplicate_overlapping_events(
        enriched,
        int(settings.get("minimum_event_gap_days", 30)),
    )
    primary = int(settings.get("primary_horizon_days", 90))
    mature = enriched.loc[pd.to_numeric(enriched.get(f"return_{primary}d"), errors="coerce").notna()].copy() if not enriched.empty else pd.DataFrame()
    state["mature_event_count"] = int(len(mature))
    minimum_total = int(settings.get("minimum_mature_events", 40))
    if len(mature) < minimum_total:
        state["status"] = "insufficient_history"
        state["required_mature_events"] = minimum_total
        _write_json(learning_state_path(project_root), state)
        return state

    effective_screen = dict(config.get("screen", {}))
    effective_screen.update(active)
    evaluations: list[dict[str, Any]] = []
    for spec in RULE_SPECS:
        if spec.config_key not in effective_screen or spec.metric not in mature.columns:
            continue
        try:
            current = float(effective_screen[spec.config_key])
        except (TypeError, ValueError):
            continue
        for candidate in _candidate_values(spec, current):
            result = _evaluate_candidate(mature, spec, current, candidate, settings)
            if result is not None:
                evaluations.append(result)

    state["evaluated_candidates"] = evaluations
    accepted = [item for item in evaluations if item.get("accepted")]
    if not accepted:
        state["status"] = "no_robust_improvement"
        _write_json(learning_state_path(project_root), state)
        return state

    best = max(accepted, key=lambda item: float(item.get("score", float("-inf"))))
    state["best_proposal"] = best
    state["status"] = "proposal_ready"
    if bool(settings.get("auto_apply", True)):
        new_active = dict(active)
        new_active[str(best["rule"])] = best["candidate"]
        payload = {
            "schema_version": 1,
            "updated_at": _now_iso(),
            "screen": new_active,
            "last_change": best,
            "source_signature": signature,
            "notice": "Runtime overlay learned from point-in-time history. Source YAML is unchanged and rollback remains possible.",
        }
        _write_json(active_rules_path(project_root), payload)
        state["active_screen_overrides"] = new_active
        state["last_applied_at"] = payload["updated_at"]
        state["last_applied_change"] = best
        state["status"] = "auto_applied"
        _append_audit(
            project_root,
            {"at": payload["updated_at"], "action": "auto_apply", "change": best, "screen": new_active},
        )
    _write_json(learning_state_path(project_root), state)
    return state


def refresh_and_apply_rule_learning(
    config_path: str | Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Refresh local learning state and overlay accepted rules onto one loaded config.

    This function never performs market-data or network access. It uses only persisted
    point-in-time analysis history plus the already configured local price dataset.
    """
    if not bool(config.get("rule_learning", {}).get("enabled", False)):
        return config
    project_root = Path(config_path).resolve().parent.parent
    refresh_rule_learning_state(project_root, config)
    return apply_active_rule_overrides(config, project_root)
