from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd

ANALYSIS_HISTORY_COLUMNS = [
    "analysis_date", "data_as_of", "run_id", "code", "name", "market", "sector", "selection_strategy",
    "selected_for_review", "strategy_score", "quantitative_score", "daytrade_activity_score",
    "close", "drawdown_52w", "relative_return_6m", "sales_cagr_3y", "operating_margin",
    "operating_cf_positive_ratio_3y", "equity_ratio", "forecast_op_growth",
    "forecast_dividend_yield", "payout_ratio", "forecast_dividend_change_rate", "benchmark_source", "volatility_60d", "average_intraday_range_20d",
    "average_turnover_yen_20d", "pass_reasons", "fail_reasons", "warning_reasons",
]
CONDITION_RULES = [
    ("売上CAGR 3%以上", "sales_cagr_3y", ">=", 0.03),
    ("営業利益率 10%以上", "operating_margin", ">=", 0.10),
    ("自己資本比率 40%以上", "equity_ratio", ">=", 0.40),
    ("52週高値から20%以上下落", "drawdown_52w", "<=", -0.20),
    ("市場比10%以上劣後", "relative_return_6m", "<=", -0.10),
    ("会社予想営業利益が増益", "forecast_op_growth", ">=", 0.0),
    ("予想配当利回り 3%以上", "forecast_dividend_yield", ">=", 0.03),
    ("60日ボラ 35%以上", "volatility_60d", ">=", 0.35),
    ("20日平均日中値幅 2.5%以上", "average_intraday_range_20d", ">=", 0.025),
]

STAR_OUTCOME_HORIZONS = (10, 20, 30, 60, 90, 180)


def history_root(project_root: Path) -> Path:
    return Path(project_root) / "data" / "history"


def _safe_code_series(frame: pd.DataFrame) -> pd.Series:
    return frame.get("code", pd.Series(index=frame.index, dtype=str)).astype(str)


def _numeric_column(frame: pd.DataFrame, column: str) -> pd.Series:
    """Return one numeric Series even when an older persisted frame lacks the column."""
    if column not in frame.columns:
        return pd.Series(index=frame.index, dtype=float)
    values = frame[column]
    if isinstance(values, pd.DataFrame):
        # Defensive compatibility for accidentally duplicated persisted columns.
        values = values.iloc[:, -1] if values.shape[1] else pd.Series(index=frame.index, dtype=float)
    return pd.to_numeric(values, errors="coerce")


def _coerce_bool_series(series: pd.Series | pd.DataFrame) -> pd.Series:
    """Coerce persisted bool-like values to one stable 1-D boolean mask.

    Older history CSVs or concatenated frames can occasionally expose duplicate
    ``selected_for_review`` columns.  In that case ``frame["selected_for_review"]``
    is a DataFrame, not a Series, and passing it through to ``.loc`` can fail with
    ``TypeError: unhashable type: 'Series'`` on some pandas versions.  Collapse
    duplicate columns row-wise (any true wins so a real review candidate is never
    hidden), and always return an ordinary boolean Series.
    """
    if isinstance(series, pd.DataFrame):
        if series.shape[1] == 0:
            return pd.Series(False, index=series.index, dtype=bool)
        parts = [_coerce_bool_series(series.iloc[:, i]) for i in range(series.shape[1])]
        combined = pd.concat(parts, axis=1).any(axis=1)
        return pd.Series(combined.to_numpy(dtype=bool), index=series.index, dtype=bool)

    if not isinstance(series, pd.Series):
        series = pd.Series(series)
    if pd.api.types.is_bool_dtype(series):
        values = series.fillna(False).astype(bool).to_numpy(dtype=bool)
        return pd.Series(values, index=series.index, dtype=bool)
    numeric = pd.to_numeric(series, errors="coerce")
    text = series.astype("string").str.strip().str.lower()
    truthy = text.isin({"true", "t", "yes", "y", "on"}) | numeric.eq(1)
    values = truthy.fillna(False).to_numpy(dtype=bool)
    return pd.Series(values, index=series.index, dtype=bool)


def _analysis_snapshot_payload(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the stable analytical payload used to detect duplicate daily snapshots."""
    payload = frame.copy()
    payload = payload.drop(columns=["analysis_date", "run_id"], errors="ignore")
    if "code" in payload.columns:
        payload["code"] = payload["code"].astype(str)
    cols = sorted(payload.columns)
    payload = payload[cols]
    sort_cols = [c for c in ["code", "selection_strategy"] if c in payload.columns]
    if sort_cols:
        payload = payload.sort_values(sort_cols, kind="stable")
    return payload.reset_index(drop=True)


def _analysis_snapshot_fingerprint(frame: pd.DataFrame) -> tuple[int, int]:
    """Stable in-process fingerprint for equality checks of analytical snapshot contents."""
    payload = _analysis_snapshot_payload(frame)
    if payload.empty:
        return (0, 0)
    hashed = pd.util.hash_pandas_object(payload, index=False).astype("uint64")
    # Pair row count with a uint64 sum; exact equality is still verified before suppressing a write.
    return (len(payload), int(hashed.sum()))


def _same_analysis_snapshot(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    if _analysis_snapshot_fingerprint(left) != _analysis_snapshot_fingerprint(right):
        return False
    try:
        pd.testing.assert_frame_equal(
            _analysis_snapshot_payload(left),
            _analysis_snapshot_payload(right),
            check_dtype=False,
            check_like=False,
        )
        return True
    except AssertionError:
        return False


def write_daily_analysis_snapshot(project_root: Path, audit: pd.DataFrame, *, analysis_date: date | str, run_id: str, data_as_of: date | str | None = None) -> Path:
    """Persist one point-in-time quantitative snapshot.

    A same-day rerun replaces that day.  When a later execution sees exactly the
    same analytical payload and the same ``data_as_of`` as the most recent prior
    day, no duplicate day is created.  This prevents weekend/non-market reruns
    from manufacturing thousands of fresh ``未評価`` rows.
    """
    target_dir = history_root(project_root) / "analysis"
    target_dir.mkdir(parents=True, exist_ok=True)
    day = pd.Timestamp(analysis_date).date().isoformat()
    frame = audit.copy()
    frame["analysis_date"] = day
    frame["data_as_of"] = pd.Timestamp(data_as_of).date().isoformat() if data_as_of is not None else day
    frame["run_id"] = str(run_id)
    frame["code"] = _safe_code_series(frame)
    cols = [c for c in ANALYSIS_HISTORY_COLUMNS if c in frame.columns]
    current_snapshot = frame[cols].copy()
    path = target_dir / f"{day}.csv.gz"

    # Same-day reruns remain replaceable.  Only suppress a *new date* whose
    # market/data timestamp and full analytical payload are unchanged.
    prior_paths = sorted(p for p in target_dir.glob("????-??-??.csv.gz") if p.name[:10] < day)
    if prior_paths:
        previous_path = prior_paths[-1]
        try:
            previous = pd.read_csv(previous_path, dtype={"code": str}, compression="gzip")
        except Exception:
            previous = pd.DataFrame()
        if not previous.empty:
            prev_as_of = str(previous.get("data_as_of", pd.Series(dtype=str)).iloc[0]) if "data_as_of" in previous.columns else ""
            curr_as_of = str(current_snapshot.get("data_as_of", pd.Series(dtype=str)).iloc[0]) if "data_as_of" in current_snapshot.columns else ""
            if prev_as_of == curr_as_of and _same_analysis_snapshot(previous, current_snapshot):
                return previous_path

    current_snapshot.to_csv(path, index=False, encoding="utf-8-sig", compression="gzip")
    return path


def load_analysis_history(project_root: Path, *, start: date | None = None, end: date | None = None, selected_only: bool = False) -> pd.DataFrame:
    folder = history_root(project_root) / "analysis"
    if not folder.exists():
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    previous_effective: pd.DataFrame | None = None
    previous_as_of = ""
    for path in sorted(folder.glob("????-??-??.csv.gz")):
        try:
            day = pd.Timestamp(path.name[:10]).date()
        except Exception:
            continue
        if start and day < start:
            continue
        if end and day > end:
            continue
        try:
            frame = pd.read_csv(path, dtype={"code": str}, compression="gzip")
        except Exception:
            continue

        # Backward repair for already-created weekend/non-market duplicates:
        # hide a later day only when the data timestamp and complete analytical
        # payload are unchanged.  Distinct criteria/results are never collapsed.
        current_as_of = str(frame.get("data_as_of", pd.Series(dtype=str)).iloc[0]) if (not frame.empty and "data_as_of" in frame.columns) else ""
        if previous_effective is not None and current_as_of == previous_as_of and _same_analysis_snapshot(previous_effective, frame):
            continue
        frames.append(frame)
        previous_effective = frame
        previous_as_of = current_as_of
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    if selected_only and "selected_for_review" in out.columns:
        out = out.loc[_coerce_bool_series(out["selected_for_review"])].copy()
    return out



UNASSESSED_REASON_NO_RECORD = "評価履歴なし"
UNASSESSED_REASON_YAHOO_FAILED = "Yahoo取得失敗"
UNASSESSED_REASON_YAHOO_BULK_LIMIT = "Yahoo100件制限で未実施"
UNASSESSED_REASON_LEGACY = "旧履歴"
UNASSESSED_REASON_INSUFFICIENT_HISTORY = "履歴不足／再現不能"
UNASSESSED_REASON_OTHER = "その他"
EVALUATION_STATUS_SAME_DAY = "当日評価済み"
EVALUATION_STATUS_BACKFILLED = "後日補完"
EVALUATION_STATUS_UNASSESSED = "未評価"
EVALUATION_STATUS_NOT_APPLICABLE = "評価対象外"
UNASSESSED_REASON_NOT_SELECTED = "定量候補外"


def _infer_evaluation_status_and_reason(row: pd.Series | dict) -> tuple[str, str]:
    raw_status = row.get("evaluation_status", "")
    raw_reason = row.get("unassessed_reason", "")
    status = "" if pd.isna(raw_status) else str(raw_status).strip()
    reason = "" if pd.isna(raw_reason) else str(raw_reason).strip()
    if status in {EVALUATION_STATUS_SAME_DAY, EVALUATION_STATUS_BACKFILLED}:
        return status, ""
    if status == EVALUATION_STATUS_UNASSESSED and reason:
        return status, reason

    trend_raw = row.get("latest_trend", "")
    note_raw = row.get("decision_note", "")
    symbol_raw = row.get("intuitive_symbol", "")
    trend = "" if pd.isna(trend_raw) else str(trend_raw)
    note = "" if pd.isna(note_raw) else str(note_raw)
    symbol = "" if pd.isna(symbol_raw) else str(symbol_raw).strip()
    price = pd.to_numeric(pd.Series([row.get("latest_price")]), errors="coerce").iloc[0]
    if trend.startswith("未実施（100件以上）") or "100件以上" in note:
        return EVALUATION_STATUS_UNASSESSED, UNASSESSED_REASON_YAHOO_BULK_LIMIT
    if trend.startswith("取得不能") or "外部株価履歴を取得できませんでした" in note:
        return EVALUATION_STATUS_UNASSESSED, UNASSESSED_REASON_YAHOO_FAILED
    # Backward compatibility: older saved evaluation rows may contain only the
    # final symbol. Treat those as assessed instead of retroactively losing it.
    if symbol and not trend and pd.isna(price):
        return EVALUATION_STATUS_SAME_DAY, ""
    if pd.isna(price):
        return EVALUATION_STATUS_UNASSESSED, UNASSESSED_REASON_YAHOO_FAILED
    if symbol:
        return EVALUATION_STATUS_SAME_DAY, ""
    return EVALUATION_STATUS_UNASSESSED, UNASSESSED_REASON_OTHER


def attach_daily_final_evaluations(analysis: pd.DataFrame, evaluations: pd.DataFrame) -> pd.DataFrame:
    """Attach same-day final evaluation plus data-quality status to analysis history.

    ``selected_for_review`` is the quantitative-screen flag. ``final_evaluation``
    is the later-stage ◎☆/◎/○/△/× result. Missing results are never silently
    conflated: ``evaluation_status`` and ``unassessed_reason`` explain why a row
    remains ``未評価``. Backfilled results preserve ``original_final_evaluation``.
    """
    if analysis.empty:
        out = analysis.copy()
        for col in ["final_evaluation", "evaluation_status", "unassessed_reason", "original_final_evaluation", "original_unassessed_reason", "evaluated_at", "evaluation_as_of"]:
            if col not in out.columns:
                out[col] = pd.Series(dtype=str)
        return out

    out = analysis.copy()
    out["code"] = _safe_code_series(out)
    out["analysis_date"] = pd.to_datetime(out.get("analysis_date"), errors="coerce").dt.date.astype(str)
    selected = _coerce_bool_series(out["selected_for_review"]) if "selected_for_review" in out.columns else pd.Series(True, index=out.index, dtype=bool)

    if evaluations.empty or "intuitive_symbol" not in evaluations.columns:
        out["final_evaluation"] = "未評価"
        out["evaluation_status"] = EVALUATION_STATUS_UNASSESSED
        out["unassessed_reason"] = UNASSESSED_REASON_NO_RECORD
        out["original_final_evaluation"] = "未評価"
        out["original_unassessed_reason"] = UNASSESSED_REASON_NO_RECORD
        out["evaluated_at"] = ""
        out["evaluation_as_of"] = out["analysis_date"]
        not_selected = ~selected.to_numpy(dtype=bool)
        out.loc[not_selected, "final_evaluation"] = "対象外"
        out.loc[not_selected, "evaluation_status"] = EVALUATION_STATUS_NOT_APPLICABLE
        out.loc[not_selected, "unassessed_reason"] = UNASSESSED_REASON_NOT_SELECTED
        out.loc[not_selected, "original_final_evaluation"] = "対象外"
        out.loc[not_selected, "original_unassessed_reason"] = UNASSESSED_REASON_NOT_SELECTED
        return out

    ev = evaluations.copy()
    if "code" not in ev.columns or "evaluation_date" not in ev.columns:
        out["final_evaluation"] = "未評価"
        out["evaluation_status"] = EVALUATION_STATUS_UNASSESSED
        out["unassessed_reason"] = UNASSESSED_REASON_NO_RECORD
        out["original_final_evaluation"] = "未評価"
        out["original_unassessed_reason"] = UNASSESSED_REASON_NO_RECORD
        out["evaluated_at"] = ""
        out["evaluation_as_of"] = out["analysis_date"]
        not_selected = ~selected.to_numpy(dtype=bool)
        out.loc[not_selected, "final_evaluation"] = "対象外"
        out.loc[not_selected, "evaluation_status"] = EVALUATION_STATUS_NOT_APPLICABLE
        out.loc[not_selected, "unassessed_reason"] = UNASSESSED_REASON_NOT_SELECTED
        out.loc[not_selected, "original_final_evaluation"] = "対象外"
        out.loc[not_selected, "original_unassessed_reason"] = UNASSESSED_REASON_NOT_SELECTED
        return out

    ev["code"] = ev["code"].astype(str)
    ev["analysis_date"] = pd.to_datetime(ev["evaluation_date"], errors="coerce").dt.date.astype(str)
    inferred = ev.apply(_infer_evaluation_status_and_reason, axis=1, result_type="expand")
    ev["evaluation_status"] = inferred[0]
    ev["unassessed_reason"] = inferred[1]
    for col, default in [
        ("original_final_evaluation", ""), ("original_unassessed_reason", ""), ("evaluated_at", ""), ("evaluation_as_of", "")
    ]:
        if col not in ev.columns:
            ev[col] = default

    join_keys = ["analysis_date", "code"]
    if "selection_strategy" in out.columns and "selection_strategy" in ev.columns:
        join_keys.append("selection_strategy")
    cols = join_keys + [
        "intuitive_symbol", "evaluation_status", "unassessed_reason",
        "original_final_evaluation", "original_unassessed_reason", "evaluated_at", "evaluation_as_of",
    ]
    latest = ev[cols].drop_duplicates(join_keys, keep="last")
    latest = latest.rename(columns={"intuitive_symbol": "_saved_final_evaluation"})
    out = out.merge(latest, on=join_keys, how="left")

    earliest_eval = pd.to_datetime(ev["analysis_date"], errors="coerce").min()
    missing = out["evaluation_status"].isna()
    out.loc[missing, "evaluation_status"] = EVALUATION_STATUS_UNASSESSED
    if pd.notna(earliest_eval):
        dates = pd.to_datetime(out.loc[missing, "analysis_date"], errors="coerce")
        legacy_idx = dates.loc[dates < earliest_eval].index
        out.loc[legacy_idx, "unassessed_reason"] = UNASSESSED_REASON_LEGACY
    out.loc[missing & out["unassessed_reason"].isna(), "unassessed_reason"] = UNASSESSED_REASON_NO_RECORD

    completed = out["evaluation_status"].isin({EVALUATION_STATUS_SAME_DAY, EVALUATION_STATUS_BACKFILLED})
    out["final_evaluation"] = "未評価"
    out.loc[completed, "final_evaluation"] = out.loc[completed, "_saved_final_evaluation"].fillna("未評価").astype(str)
    out["unassessed_reason"] = out["unassessed_reason"].fillna("").astype(str)
    out.loc[completed, "unassessed_reason"] = ""
    out["original_final_evaluation"] = out["original_final_evaluation"].fillna("").astype(str)
    out.loc[(out["evaluation_status"] == EVALUATION_STATUS_BACKFILLED) & (out["original_final_evaluation"] == ""), "original_final_evaluation"] = "未評価"
    out.loc[out["evaluation_status"] == EVALUATION_STATUS_UNASSESSED, "original_final_evaluation"] = "未評価"
    out["original_unassessed_reason"] = out["original_unassessed_reason"].fillna("").astype(str)
    out.loc[(out["evaluation_status"] == EVALUATION_STATUS_UNASSESSED) & (out["original_unassessed_reason"] == ""), "original_unassessed_reason"] = out.loc[(out["evaluation_status"] == EVALUATION_STATUS_UNASSESSED) & (out["original_unassessed_reason"] == ""), "unassessed_reason"]
    out["evaluated_at"] = out["evaluated_at"].fillna("").astype(str)
    out["evaluation_as_of"] = out["evaluation_as_of"].fillna(out["analysis_date"]).astype(str)

    # Quantitative non-candidates are not unresolved evaluations. They were never
    # supposed to receive the Yahoo-backed final ◎☆/◎/○/△/× review. Keep them
    # visible when selected_only=False, but classify them separately so they do
    # not reappear in the actionable ``未評価`` queue.
    not_selected = ~selected.to_numpy(dtype=bool)
    out.loc[not_selected, "final_evaluation"] = "対象外"
    out.loc[not_selected, "evaluation_status"] = EVALUATION_STATUS_NOT_APPLICABLE
    out.loc[not_selected, "unassessed_reason"] = UNASSESSED_REASON_NOT_SELECTED
    out.loc[not_selected, "original_final_evaluation"] = "対象外"
    out.loc[not_selected, "original_unassessed_reason"] = UNASSESSED_REASON_NOT_SELECTED
    out.loc[not_selected, "evaluated_at"] = ""
    out.loc[not_selected, "evaluation_as_of"] = out.loc[not_selected, "analysis_date"]
    return out.drop(columns=["_saved_final_evaluation"], errors="ignore")


def select_slow_revaluation_batch(unassessed: pd.DataFrame, *, batch_size: int = 20) -> pd.DataFrame:
    """Return at most ``batch_size`` unique codes for resumable slow revaluation.

    All rows belonging to the selected codes are returned so one Yahoo history fetch
    can rebuild multiple analysis dates for the same security.  The function is pure
    and performs no network access.
    """
    if unassessed is None or unassessed.empty:
        return pd.DataFrame(columns=getattr(unassessed, "columns", None))
    size = max(1, int(batch_size))
    if "code" not in unassessed.columns:
        return unassessed.iloc[0:0].copy()
    codes = (
        unassessed["code"]
        .dropna()
        .astype(str)
        .loc[lambda s: s.str.strip() != ""]
        .drop_duplicates()
        .sort_values(kind="stable")
        .head(size)
        .tolist()
    )
    return unassessed.loc[unassessed["code"].astype(str).isin(codes)].copy()


def revaluate_unassessed_rows(
    analysis_rows: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    *,
    evaluated_at: str,
) -> pd.DataFrame:
    """Rebuild historical final evaluations using only market data available by that day.

    This function performs no network access. Callers supply Yahoo daily histories, and
    each history is cut off at ``analysis_date`` before trend/readiness calculations so
    future data cannot leak into the reconstructed decision.
    """
    if analysis_rows.empty:
        return pd.DataFrame()
    from value_dislocation.decision import build_buy_readiness, build_intuitive_signal, build_trend_transition

    rows: list[dict] = []
    for _, source in analysis_rows.iterrows():
        code = str(source.get("code", ""))
        target_date = pd.to_datetime(source.get("analysis_date"), errors="coerce")
        strategy = str(source.get("selection_strategy", "value_dislocation"))
        result = {
            "evaluation_date": target_date.date().isoformat() if pd.notna(target_date) else "",
            "analysis_as_of": source.get("data_as_of"),
            "code": code,
            "name": source.get("name", ""),
            "market": source.get("market", ""),
            "selection_strategy": strategy,
            "intuitive_symbol": "",
            "strategy_score": source.get("strategy_score", source.get("quantitative_score")),
            "latest_price": None,
            "latest_market_date": None,
            "latest_trend": "取得不能",
            "trend_transition": "判定不能",
            "invalidation_status": "",
            "decision_note": "",
            "evaluation_status": EVALUATION_STATUS_UNASSESSED,
            "unassessed_reason": UNASSESSED_REASON_INSUFFICIENT_HISTORY,
            "original_final_evaluation": "未評価",
            "original_unassessed_reason": str(source.get("unassessed_reason", "") or ""),
            "evaluated_at": str(evaluated_at),
            "evaluation_as_of": target_date.date().isoformat() if pd.notna(target_date) else "",
        }
        if pd.isna(target_date):
            result["decision_note"] = "分析日を特定できないため後日補完できません。"
            rows.append(result)
            continue
        if strategy != "value_dislocation":
            result["decision_note"] = "この抽出ルールは◎☆/◎/○/△/×の後日補完対象外です。"
            rows.append(result)
            continue
        history = histories.get(code)
        if history is None or history.empty or not {"date", "close"}.issubset(history.columns):
            result["unassessed_reason"] = UNASSESSED_REASON_YAHOO_FAILED
            result["decision_note"] = "Yahoo過去日足を取得できず、後日補完できませんでした。"
            rows.append(result)
            continue
        h = history.copy()
        h["date"] = pd.to_datetime(h["date"], errors="coerce").dt.tz_localize(None)
        h = h.dropna(subset=["date"]).sort_values("date")
        # Critical point-in-time guard: never use prices after the original analysis day.
        h = h.loc[h["date"].dt.normalize() <= target_date.tz_localize(None).normalize()].copy()
        h["close"] = pd.to_numeric(h["close"], errors="coerce")
        h = h.dropna(subset=["close"])
        if h.empty:
            result["decision_note"] = "評価対象日以前のYahoo日足がなく、後日補完できませんでした。"
            rows.append(result)
            continue

        transition = build_trend_transition(h, lookback_days=90)
        current = transition.get("current", {})
        benchmark_source = str(source.get("benchmark_source", "") or "")
        relative_value = pd.to_numeric(pd.Series([source.get("relative_return_6m")]), errors="coerce").iloc[0]
        benchmark_available = (
            benchmark_source in {"official_topix", "topix_etf_proxy"}
            if benchmark_source
            else bool(pd.notna(relative_value))
        )
        readiness = build_buy_readiness(
            source.to_dict(),
            external_quote_available=True,
            benchmark_available=benchmark_available,
            trend=current,
        )
        intuitive = build_intuitive_signal(readiness, transition)
        latest_market_date = pd.Timestamp(h["date"].max()).date().isoformat()
        result.update({
            "intuitive_symbol": intuitive.get("symbol", ""),
            "latest_price": current.get("latest_price"),
            "latest_market_date": latest_market_date,
            "latest_trend": transition.get("current_state", "データ不足"),
            "trend_transition": transition.get("transition_state", "判定不能"),
            "decision_note": "後日補完。評価対象日より後の株価は使用していません。 " + str(transition.get("summary", "")),
            "evaluation_status": EVALUATION_STATUS_BACKFILLED,
            "unassessed_reason": "",
        })
        rows.append(result)
    return pd.DataFrame(rows)


def upsert_daily_evaluations(project_root: Path, rows: pd.DataFrame, *, evaluation_date: date | str, analysis_as_of: date | str | None = None) -> Path:
    """Upsert the current unified-candidate evaluation once per date/code/strategy."""
    folder = history_root(project_root) / "evaluations"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "evaluations.csv.gz"
    incoming = rows.copy()
    day = pd.Timestamp(evaluation_date).date().isoformat()
    incoming["evaluation_date"] = day
    incoming["analysis_as_of"] = pd.Timestamp(analysis_as_of).date().isoformat() if analysis_as_of is not None else None
    if "raw_code" in incoming.columns:
        incoming["code"] = incoming["raw_code"].astype(str)
    elif "code" in incoming.columns:
        incoming["code"] = incoming["code"].astype(str)
    else:
        incoming["code"] = ""
    if "直感判定" in incoming.columns:
        incoming["intuitive_symbol"] = incoming["直感判定"].astype(str).str.split().str[0]
    elif "intuitive_symbol" not in incoming.columns:
        incoming["intuitive_symbol"] = ""
    rename = {
        "企業名": "name", "市場": "market", "最新株価": "latest_price", "最新判定": "latest_trend",
        "変化": "trend_transition", "仮説警告": "invalidation_status", "定量スコア": "strategy_score",
        "判断メモ": "decision_note",
    }
    incoming = incoming.rename(columns={k:v for k,v in rename.items() if k in incoming.columns})
    keep = [c for c in [
        "evaluation_date", "analysis_as_of", "code", "name", "market", "selection_strategy",
        "intuitive_symbol", "strategy_score", "latest_price", "latest_market_date", "latest_trend",
        "trend_transition", "invalidation_status", "decision_note", "evaluation_status",
        "unassessed_reason", "original_final_evaluation", "original_unassessed_reason", "evaluated_at", "evaluation_as_of"
    ] if c in incoming.columns]
    incoming = incoming[keep].copy()
    if path.exists():
        try:
            current = pd.read_csv(path, dtype={"code": str}, compression="gzip")
        except Exception:
            current = pd.DataFrame()
        combined = pd.concat([current, incoming], ignore_index=True, sort=False)
    else:
        combined = incoming
    keys = [c for c in ["evaluation_date", "code", "selection_strategy"] if c in combined.columns]
    if keys:
        combined = combined.drop_duplicates(keys, keep="last")
    combined = combined.sort_values([c for c in ["evaluation_date", "code"] if c in combined.columns])
    combined.to_csv(path, index=False, encoding="utf-8-sig", compression="gzip")
    combined.to_csv(folder / "evaluations.csv", index=False, encoding="utf-8-sig")
    return path


def load_evaluation_history(project_root: Path) -> pd.DataFrame:
    path = history_root(project_root) / "evaluations" / "evaluations.csv.gz"
    if not path.exists():
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path, dtype={"code": str}, compression="gzip")
    except Exception:
        return pd.DataFrame()
    if "code" in frame.columns:
        frame["code"] = frame["code"].astype(str)
    return frame


def build_star_events(evaluations: pd.DataFrame, horizons: Iterable[int] = STAR_OUTCOME_HORIZONS) -> pd.DataFrame:
    """Build one event per observed transition into ◎☆ and compute saved-price forward returns.

    Rows whose Yahoo evaluation was skipped/failed do not end an existing star episode.
    Calendar horizons are measured from the actual latest_market_date when available.
    """
    if evaluations.empty or "intuitive_symbol" not in evaluations.columns:
        return pd.DataFrame()
    frame = evaluations.copy()
    frame["evaluation_date"] = pd.to_datetime(frame["evaluation_date"], errors="coerce")
    frame["latest_price"] = pd.to_numeric(frame.get("latest_price"), errors="coerce")
    market_dates = pd.to_datetime(frame.get("latest_market_date"), errors="coerce") if "latest_market_date" in frame.columns else pd.Series(pd.NaT, index=frame.index)
    frame["observation_date"] = market_dates.fillna(frame["evaluation_date"])
    frame = frame.dropna(subset=["evaluation_date"]).sort_values(["code", "evaluation_date"])
    events: list[dict] = []
    for code, group in frame.groupby("code", sort=False):
        g = group.sort_values("evaluation_date").reset_index(drop=True)
        prev_star = False
        for _, row in g.iterrows():
            valid_observation = pd.notna(row.get("latest_price")) and not str(row.get("latest_trend", "")).startswith(("未実施", "取得不能"))
            if not valid_observation:
                continue
            is_star = str(row.get("intuitive_symbol", "")) == "◎☆"
            if is_star and not prev_star:
                event = row.to_dict()
                event["star_date"] = pd.Timestamp(row["observation_date"]).date().isoformat()
                event["entry_price"] = float(row["latest_price"])
                for horizon in horizons:
                    target = pd.Timestamp(row["observation_date"]) + pd.to_timedelta(int(horizon), unit="D")
                    future = g.loc[(g["observation_date"] >= target) & pd.to_numeric(g["latest_price"], errors="coerce").notna()]
                    if future.empty:
                        event[f"return_{horizon}d"] = None
                        event[f"actual_days_{horizon}d"] = None
                    else:
                        f = future.iloc[0]
                        event[f"return_{horizon}d"] = float(f["latest_price"] / row["latest_price"] - 1.0)
                        event[f"actual_days_{horizon}d"] = int((pd.Timestamp(f["observation_date"]) - pd.Timestamp(row["observation_date"])).days)
                events.append(event)
            prev_star = is_star
    return pd.DataFrame(events)




def reconcile_star_outcomes(evaluations: pd.DataFrame, saved_events: pd.DataFrame | None = None) -> pd.DataFrame:
    """Rebuild the complete ◎☆ event set from evaluation history while preserving saved outcomes.

    Evaluation history is the source of truth for which star events exist.  Saved
    10/20/30/60/90/180-day returns are carried forward by (code, star_date), so adding an
    older/missing event never discards already-enriched forward-return data.
    """
    rebuilt = build_star_events(evaluations)
    if rebuilt.empty:
        return rebuilt
    saved = pd.DataFrame() if saved_events is None else saved_events.copy()
    if saved.empty or not {"code", "star_date"}.issubset(saved.columns):
        return rebuilt.sort_values(["star_date", "code"], ascending=[True, True]).reset_index(drop=True)

    rebuilt = rebuilt.copy()
    saved = saved.copy()
    rebuilt["code"] = rebuilt["code"].astype(str)
    saved["code"] = saved["code"].astype(str)
    rebuilt["star_date"] = rebuilt["star_date"].astype(str)
    saved["star_date"] = saved["star_date"].astype(str)
    saved_by_key = saved.drop_duplicates(["code", "star_date"], keep="last").set_index(["code", "star_date"])
    preserve = ["entry_price"]
    for horizon in STAR_OUTCOME_HORIZONS:
        preserve.extend([f"return_{horizon}d", f"actual_days_{horizon}d"])
    for idx, row in rebuilt.iterrows():
        key = (str(row.get("code", "")), str(row.get("star_date", "")))
        if key not in saved_by_key.index:
            continue
        prior = saved_by_key.loc[key]
        for col in preserve:
            if col not in saved_by_key.columns:
                continue
            value = prior.get(col)
            if pd.notna(value):
                rebuilt.at[idx, col] = value
    return rebuilt.sort_values(["star_date", "code"], ascending=[True, True]).reset_index(drop=True)

def enrich_star_events_with_market_histories(star_events: pd.DataFrame, histories: dict[str, pd.DataFrame], horizons: Iterable[int] = STAR_OUTCOME_HORIZONS) -> pd.DataFrame:
    """Fill forward returns from externally supplied daily histories without fetching data here."""
    if star_events.empty:
        return star_events.copy()
    out = star_events.copy()
    for idx, event in out.iterrows():
        code = str(event.get("code", ""))
        history = histories.get(code)
        if history is None or history.empty or not {"date", "close"}.issubset(history.columns):
            continue
        h = history.copy()
        h["date"] = pd.to_datetime(h["date"], errors="coerce").dt.tz_localize(None)
        h["close"] = pd.to_numeric(h["close"], errors="coerce")
        h = h.dropna(subset=["date", "close"]).sort_values("date")
        if h.empty:
            continue
        start = pd.Timestamp(event.get("star_date"))
        entry = pd.to_numeric(pd.Series([event.get("entry_price")]), errors="coerce").iloc[0]
        if pd.isna(entry) or float(entry) <= 0:
            entry_rows = h.loc[h["date"] >= start]
            if entry_rows.empty:
                continue
            entry = float(entry_rows.iloc[0]["close"])
            out.at[idx, "entry_price"] = entry
            start = pd.Timestamp(entry_rows.iloc[0]["date"])
            out.at[idx, "star_date"] = start.date().isoformat()
        for horizon in horizons:
            target = start + pd.to_timedelta(int(horizon), unit="D")
            future = h.loc[h["date"] >= target]
            if future.empty:
                continue
            row = future.iloc[0]
            out.at[idx, f"return_{horizon}d"] = float(row["close"] / float(entry) - 1.0)
            out.at[idx, f"actual_days_{horizon}d"] = int((pd.Timestamp(row["date"]) - start).days)
    return out



def summarize_star_outcomes_by_code(events: pd.DataFrame) -> pd.DataFrame:
    """Summarize ◎☆ start events to one row per security code.

    Event-level rows remain the source of truth.  This helper is only a view-layer
    summary: repeated transitions into ◎☆ are collapsed by code while preserving
    the first/latest dates, event count, latest entry price and mean matured
    10/20/30/60/90/180-day returns.
    """
    if events is None or events.empty or "code" not in events.columns:
        return pd.DataFrame()

    frame = events.copy()
    frame["code"] = frame["code"].astype(str)
    frame["_star_date"] = pd.to_datetime(frame.get("star_date"), errors="coerce")
    frame["_entry_price"] = pd.to_numeric(frame.get("entry_price"), errors="coerce")
    for horizon in STAR_OUTCOME_HORIZONS:
        frame[f"_return_{horizon}d"] = _numeric_column(frame, f"return_{horizon}d")

    rows: list[dict] = []
    for code, group in frame.groupby("code", sort=False, dropna=False):
        g = group.sort_values("_star_date", kind="stable")
        valid_dates = g["_star_date"].dropna()
        latest = g.iloc[-1]
        name_values = g.get("name", pd.Series(dtype=str)).dropna().astype(str)
        name_values = name_values.loc[name_values.str.strip().ne("")]
        row = {
            "code": str(code),
            "name": name_values.iloc[-1] if len(name_values) else "",
            "first_star_date": valid_dates.iloc[0].date().isoformat() if len(valid_dates) else "",
            "latest_star_date": valid_dates.iloc[-1].date().isoformat() if len(valid_dates) else "",
            "star_count": int(len(g)),
            "latest_entry_price": latest.get("_entry_price"),
        }
        for horizon in STAR_OUTCOME_HORIZONS:
            values = g[f"_return_{horizon}d"].dropna()
            row[f"return_{horizon}d_avg"] = float(values.mean()) if len(values) else None
            row[f"completed_{horizon}d"] = int(len(values))
        rows.append(row)
    return pd.DataFrame(rows)

EVALUATION_SYMBOL_ORDER = ["◎☆", "◎", "○", "△", "×", "未評価", "対象外"]


def daily_evaluation_counts(history: pd.DataFrame) -> pd.DataFrame:
    """Aggregate history to lightweight daily final-evaluation counts for charts."""
    if history is None or history.empty or "analysis_date" not in history.columns:
        return pd.DataFrame()
    frame = history.copy()
    frame["analysis_date"] = pd.to_datetime(frame["analysis_date"], errors="coerce")
    frame = frame.loc[frame["analysis_date"].notna()].copy()
    if frame.empty:
        return pd.DataFrame()
    if "final_evaluation" not in frame.columns:
        frame["final_evaluation"] = "未評価"
    frame["final_evaluation"] = frame["final_evaluation"].fillna("未評価").astype(str).replace("", "未評価")
    result = (
        frame.groupby(["analysis_date", "final_evaluation"], dropna=False)
        .size()
        .unstack(fill_value=0)
        .sort_index()
    )
    ordered = [c for c in EVALUATION_SYMBOL_ORDER if c in result.columns]
    ordered += [c for c in result.columns if c not in ordered]
    result = result[ordered]
    result.index = result.index.strftime("%Y-%m-%d")
    return result


def evaluation_symbol_counts(evaluations: pd.DataFrame) -> pd.DataFrame:
    """Return one-row-per-symbol counts for the evaluation-history distribution chart."""
    if evaluations is None or evaluations.empty:
        return pd.DataFrame(columns=["件数"])
    if "intuitive_symbol" in evaluations.columns:
        symbols = evaluations["intuitive_symbol"].fillna("").astype(str).str.strip().replace("", "未評価")
    else:
        symbols = pd.Series("未評価", index=evaluations.index, dtype=str)
    counts = symbols.value_counts(dropna=False)
    ordered = [x for x in EVALUATION_SYMBOL_ORDER if x in counts.index]
    ordered += [str(x) for x in counts.index if str(x) not in ordered]
    return pd.DataFrame({"件数": [int(counts.get(x, 0)) for x in ordered]}, index=ordered)


def star_forward_return_summary(events: pd.DataFrame) -> pd.DataFrame:
    """Summarize matured ◎☆ forward returns by configured short/medium horizons for charts."""
    rows = []
    frame = pd.DataFrame() if events is None else events
    for horizon in STAR_OUTCOME_HORIZONS:
        values = _numeric_column(frame, f"return_{horizon}d").dropna()
        rows.append({
            "期間": f"{horizon}日",
            "平均リターン(%)": float(values.mean() * 100) if len(values) else None,
            "プラス率(%)": float((values > 0).mean() * 100) if len(values) else None,
            "確定件数": int(len(values)),
        })
    return pd.DataFrame(rows).set_index("期間")


def load_star_outcomes(project_root: Path) -> pd.DataFrame:
    path = history_root(project_root) / "outcomes" / "star_outcomes.csv.gz"
    if not path.exists():
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path, dtype={"code": str}, compression="gzip")
    except Exception:
        return pd.DataFrame()
    if "code" in frame.columns:
        frame["code"] = frame["code"].astype(str)
    return frame


def save_star_outcomes(project_root: Path, events: pd.DataFrame) -> Path:
    folder = history_root(project_root) / "outcomes"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "star_outcomes.csv.gz"
    events.to_csv(path, index=False, encoding="utf-8-sig", compression="gzip")
    events.to_csv(folder / "star_outcomes.csv", index=False, encoding="utf-8-sig")
    return path

def write_star_outcomes(project_root: Path, evaluations: pd.DataFrame | None = None) -> Path:
    events = build_star_events(load_evaluation_history(project_root) if evaluations is None else evaluations)
    return save_star_outcomes(project_root, events)


def condition_performance(project_root: Path, star_events: pd.DataFrame | None = None) -> pd.DataFrame:
    """Exploratory condition/outcome association. This is not a causal estimate."""
    events = build_star_events(load_evaluation_history(project_root)) if star_events is None else star_events.copy()
    if events.empty:
        return pd.DataFrame()
    analysis = load_analysis_history(project_root)
    if analysis.empty:
        return pd.DataFrame()
    analysis["analysis_date"] = pd.to_datetime(analysis["analysis_date"], errors="coerce")
    events["analysis_as_of"] = pd.to_datetime(events.get("analysis_as_of"), errors="coerce")
    merged_rows: list[dict] = []
    for _, event in events.iterrows():
        code = str(event.get("code", ""))
        candidates = analysis.loc[analysis["code"].astype(str) == code].copy()
        if candidates.empty:
            continue
        target = pd.Timestamp(event.get("star_date"))
        candidates = candidates.loc[candidates["analysis_date"] <= target]
        if candidates.empty:
            continue
        snap = candidates.sort_values("analysis_date").iloc[-1].to_dict()
        merged_rows.append({**snap, **event.to_dict()})
    merged = pd.DataFrame(merged_rows)
    if merged.empty:
        return merged
    result=[]
    for label, col, op, threshold in CONDITION_RULES:
        if col not in merged.columns:
            continue
        vals = pd.to_numeric(merged[col], errors="coerce")
        mask = vals >= threshold if op == ">=" else vals <= threshold
        subset = merged.loc[mask.fillna(False)]
        row={"条件": label, "該当イベント数": int(len(subset)), "全イベント数": int(len(merged))}
        for h in STAR_OUTCOME_HORIZONS:
            r = _numeric_column(subset, f"return_{h}d").dropna()
            row[f"{h}日平均"] = float(r.mean()) if not r.empty else None
            row[f"{h}日プラス率"] = float((r>0).mean()) if not r.empty else None
            row[f"{h}日確定件数"] = int(len(r))
        result.append(row)
    return pd.DataFrame(result)
