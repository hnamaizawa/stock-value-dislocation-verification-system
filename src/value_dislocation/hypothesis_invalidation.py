from __future__ import annotations

import json
import math
import operator
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

# Thresholds for ratio metrics are entered in human-friendly percent units.
METRIC_DEFINITIONS: dict[str, dict[str, str]] = {
    "sales_cagr_3y": {"label": "売上CAGR（3年）", "unit": "%", "scale": "percent"},
    "operating_margin": {"label": "営業利益率", "unit": "%", "scale": "percent"},
    "operating_profit_latest": {"label": "直近営業利益", "unit": "円", "scale": "raw"},
    "operating_cf_positive_ratio_3y": {"label": "営業CFプラス比率（直近最大3期）", "unit": "%", "scale": "percent"},
    "equity_ratio": {"label": "自己資本比率", "unit": "%", "scale": "percent"},
    "net_cash": {"label": "ネットキャッシュ", "unit": "円", "scale": "raw"},
    "forecast_operating_profit": {"label": "会社予想営業利益", "unit": "円", "scale": "raw"},
    "forecast_op_growth": {"label": "会社予想営業利益増減率", "unit": "%", "scale": "percent"},
    "forecast_annual_dividend_per_share": {"label": "予想年間配当（1株）", "unit": "円", "scale": "raw"},
    "forecast_dividend_yield": {"label": "予想配当利回り", "unit": "%", "scale": "percent"},
    "payout_ratio": {"label": "予想配当性向", "unit": "%", "scale": "percent"},
    "forecast_dividend_change_rate": {"label": "予想増配・減配率", "unit": "%", "scale": "percent"},
}

OPERATORS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
}


def metric_choices() -> list[tuple[str, str]]:
    return [(key, spec["label"]) for key, spec in METRIC_DEFINITIONS.items()]


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def format_threshold_input_value(value: Any) -> str:
    """Format an editable threshold without forcing insignificant decimal places."""
    number = _number(value)
    if number is None:
        return ""
    if number == 0:
        return "0"
    if number.is_integer():
        return str(int(number))
    return f"{number:.12f}".rstrip("0").rstrip(".")


def _threshold_to_raw(metric: str, threshold: float) -> float:
    spec = METRIC_DEFINITIONS[metric]
    return threshold / 100.0 if spec["scale"] == "percent" else threshold


def _display_value(metric: str, value: float) -> str:
    spec = METRIC_DEFINITIONS[metric]
    if spec["scale"] == "percent":
        return f"{value * 100:.2f}%"
    if spec["unit"] == "円":
        return f"¥{value:,.0f}"
    return f"{value:,.2f}"


def _display_threshold(metric: str, threshold: float) -> str:
    spec = METRIC_DEFINITIONS[metric]
    if spec["scale"] == "percent":
        return f"{threshold:.2f}%"
    if spec["unit"] == "円":
        return f"¥{threshold:,.0f}"
    return f"{threshold:,.2f}"



def structured_conditions_from_ui_rows(rows: Any) -> list[dict[str, Any]]:
    """Convert every current UI row to the persisted structured-condition schema.

    This deliberately consumes the complete row collection in one call so a save
    cannot accidentally serialize only the first committed row of a multi-row edit.
    Invalid/incomplete rows are skipped, matching the previous dashboard behavior.
    """
    if rows is None:
        return []
    result: list[dict[str, Any]] = []
    label_to_metric = {spec["label"]: key for key, spec in METRIC_DEFINITIONS.items()}
    for raw in list(rows):
        if not isinstance(raw, Mapping):
            continue
        label = str(raw.get("指標", "") or "").strip()
        metric = label_to_metric.get(label)
        threshold = _number(raw.get("閾値"))
        op = str(raw.get("比較", "") or "").strip()
        if metric is None or threshold is None or op not in OPERATORS:
            continue
        result.append({
            "metric": metric,
            "operator": op,
            "threshold": float(threshold),
            "unit": METRIC_DEFINITIONS[metric]["unit"],
            "enabled": bool(raw.get("有効", True)),
            "note": str(raw.get("メモ", "") or "").strip(),
        })
    return result

def normalize_structured_conditions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        metric = str(raw.get("metric", "")).strip()
        op = str(raw.get("operator", "")).strip()
        threshold = _number(raw.get("threshold"))
        if metric not in METRIC_DEFINITIONS or op not in OPERATORS or threshold is None:
            continue
        result.append({
            "metric": metric,
            "operator": op,
            "threshold": threshold,
            "unit": METRIC_DEFINITIONS[metric]["unit"],
            "enabled": bool(raw.get("enabled", True)),
            "note": str(raw.get("note", "")).strip(),
        })
    return result


def evaluate_hypothesis_invalidation(
    review: Mapping[str, Any] | None,
    metrics: Mapping[str, Any] | pd.Series | None,
) -> dict[str, Any]:
    """Evaluate saved invalidation conditions against already-loaded local metrics.

    This function intentionally performs no network I/O and imports no J-Quants client.
    A true condition means that the pre-declared investment hypothesis is breached.
    """
    review_doc = dict(review or {})
    metric_doc = dict(metrics or {})
    conditions = normalize_structured_conditions(review_doc.get("structured_invalidation_conditions"))
    enabled = [condition for condition in conditions if condition["enabled"]]
    evaluations: list[dict[str, Any]] = []
    breached: list[dict[str, Any]] = []
    unevaluable: list[dict[str, Any]] = []

    for condition in enabled:
        metric = condition["metric"]
        actual = _number(metric_doc.get(metric))
        threshold_display = float(condition["threshold"])
        row = {
            **condition,
            "label": METRIC_DEFINITIONS[metric]["label"],
            "actual": actual,
            "actual_display": "取得不能" if actual is None else _display_value(metric, actual),
            "threshold_display": _display_threshold(metric, threshold_display),
            "breached": None,
        }
        if actual is None:
            unevaluable.append(row)
        else:
            raw_threshold = _threshold_to_raw(metric, threshold_display)
            is_breached = bool(OPERATORS[condition["operator"]](actual, raw_threshold))
            row["breached"] = is_breached
            if is_breached:
                breached.append(row)
        evaluations.append(row)

    free_text = str(review_doc.get("invalidation_conditions", "") or "").strip()
    manual_review_required = bool(free_text)
    if breached:
        status = "breached"
    elif unevaluable:
        status = "unevaluable"
    elif enabled:
        status = "clear"
    elif manual_review_required:
        status = "manual_review"
    else:
        status = "not_configured"

    return {
        "status": status,
        "breached": breached,
        "unevaluable": unevaluable,
        "evaluations": evaluations,
        "manual_review_required": manual_review_required,
        "free_text": free_text,
        "structured_condition_count": len(enabled),
    }


def evaluate_saved_reviews(review_dir: Path, features: pd.DataFrame) -> pd.DataFrame:
    """Recalculate all saved reviews from the current feature snapshot.

    Results are derived every call. No prior result file or cached decision is read.
    Broken review files are returned as safe-side error rows rather than ignored.
    """
    feature_map: dict[str, dict[str, Any]] = {}
    if not features.empty and "code" in features.columns:
        for _, row in features.iterrows():
            digits = "".join(ch for ch in str(row.get("code", "")) if ch.isdigit())
            key = digits[:4] if len(digits) >= 4 else digits
            feature_map[key] = row.to_dict()

    rows: list[dict[str, Any]] = []
    if not review_dir.exists():
        return pd.DataFrame(rows)
    for path in sorted(review_dir.glob("*.json")):
        try:
            review = json.loads(path.read_text(encoding="utf-8"))
            code_raw = str(review.get("code", path.stem))
            digits = "".join(ch for ch in code_raw if ch.isdigit())
            code = digits[:4] if len(digits) >= 4 else digits
            result = evaluate_hypothesis_invalidation(review, feature_map.get(code, {}))
            rows.append({
                "code": code,
                "name": str(review.get("name", "")),
                "status": result["status"],
                "breach_count": len(result["breached"]),
                "unevaluable_count": len(result["unevaluable"]),
                "structured_condition_count": result["structured_condition_count"],
                "manual_review_required": result["manual_review_required"],
                "breach_details": " / ".join(
                    f"{item['label']} {item['operator']} {item['threshold_display']} (現在 {item['actual_display']})"
                    for item in result["breached"]
                ),
                "free_text": result["free_text"],
            })
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            rows.append({
                "code": path.stem,
                "name": "",
                "status": "review_error",
                "breach_count": 0,
                "unevaluable_count": 0,
                "structured_condition_count": 0,
                "manual_review_required": True,
                "breach_details": f"レビュー読込エラー: {exc}",
                "free_text": "",
            })
    return pd.DataFrame(rows)
