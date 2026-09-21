from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from value_dislocation.history import (
    STAR_OUTCOME_HORIZONS,
    EVALUATION_STATUS_BACKFILLED,
    EVALUATION_STATUS_SAME_DAY,
    attach_daily_final_evaluations,
)


DEFAULT_SIGNAL_SYMBOLS = ("◎☆",)
PEER_DISTANCE_METRICS = (
    "drawdown_52w",
    "relative_return_6m",
    "operating_margin",
    "equity_ratio",
)


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(index=frame.index, dtype=float)
    values = frame[column]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, -1]
    return pd.to_numeric(values, errors="coerce")


def _bool_mask(values, index: pd.Index) -> pd.Series:
    if isinstance(values, pd.DataFrame):
        parts = [_bool_mask(values.iloc[:, i], index) for i in range(values.shape[1])]
        if not parts:
            return pd.Series(False, index=index, dtype=bool)
        return pd.concat(parts, axis=1).any(axis=1)
    if not isinstance(values, pd.Series):
        values = pd.Series(values, index=index)
    numeric = pd.to_numeric(values, errors="coerce")
    text = values.astype("string").str.strip().str.lower()
    truthy = numeric.eq(1) | text.isin({"true", "t", "yes", "y", "on"})
    return pd.Series(truthy.fillna(False).to_numpy(dtype=bool), index=index, dtype=bool)


def _prepare_analysis(analysis: pd.DataFrame) -> pd.DataFrame:
    if analysis is None or analysis.empty:
        return pd.DataFrame()
    out = analysis.copy()
    if "code" not in out.columns or "analysis_date" not in out.columns:
        return pd.DataFrame()
    out["code"] = out["code"].astype(str)
    out["analysis_date"] = pd.to_datetime(out["analysis_date"], errors="coerce").dt.tz_localize(None)
    out["close"] = _numeric(out, "close")
    out = out.dropna(subset=["analysis_date", "code"]).sort_values(["code", "analysis_date"], kind="stable")
    return out


def _price_groups(analysis: pd.DataFrame) -> dict[str, pd.DataFrame]:
    prepared = _prepare_analysis(analysis)
    if prepared.empty:
        return {}
    prices = prepared[["code", "analysis_date", "close"]].dropna(subset=["close"]).copy()
    prices = prices.loc[prices["close"] > 0]
    prices = prices.drop_duplicates(["code", "analysis_date"], keep="last")
    return {
        str(code): group.sort_values("analysis_date", kind="stable").reset_index(drop=True)
        for code, group in prices.groupby("code", sort=False)
    }


def _forward_return(
    price_groups: dict[str, pd.DataFrame],
    code: str,
    start: pd.Timestamp,
    entry_price: float,
    horizon: int,
) -> tuple[float | None, int | None]:
    group = price_groups.get(str(code))
    if group is None or group.empty or not np.isfinite(entry_price) or entry_price <= 0:
        return None, None
    target = pd.Timestamp(start) + pd.to_timedelta(int(horizon), unit="D")
    future = group.loc[group["analysis_date"] >= target]
    if future.empty:
        return None, None
    row = future.iloc[0]
    price = float(row["close"])
    actual_days = int((pd.Timestamp(row["analysis_date"]) - pd.Timestamp(start)).days)
    return price / float(entry_price) - 1.0, actual_days


def add_external_shock_attribution(frame: pd.DataFrame) -> pd.DataFrame:
    """Decompose a six-month decline into market/sector and company-specific components.

    The calculation is deliberately conservative.  It only runs when the security's
    absolute six-month return, benchmark-relative return and sector-relative return
    were all saved at the same point in time.  Missing historical inputs stay missing;
    no benchmark or sector return is fabricated.
    """
    if frame is None or frame.empty:
        return pd.DataFrame(columns=getattr(frame, "columns", None))
    out = frame.copy()
    stock = _numeric(out, "return_6m")
    market_relative = _numeric(out, "relative_return_6m")
    sector_relative = _numeric(out, "sector_relative_return_6m")
    benchmark = stock - market_relative
    sector = stock - sector_relative
    market_decline = (-benchmark).clip(lower=0)
    sector_incremental_decline = (benchmark - sector).clip(lower=0)
    total_decline = (-stock).clip(lower=0)
    external_decline = pd.concat([total_decline, market_decline + sector_incremental_decline], axis=1).min(axis=1)
    ratio = external_decline / total_decline.where(total_decline > 0)
    valid = stock.notna() & market_relative.notna() & sector_relative.notna() & total_decline.gt(0)
    ratio = ratio.where(valid).clip(lower=0, upper=1)

    out["benchmark_return_6m_est"] = benchmark.where(valid)
    out["sector_return_6m_est"] = sector.where(valid)
    out["market_decline_component_6m"] = market_decline.where(valid)
    out["sector_decline_component_6m"] = sector_incremental_decline.where(valid)
    out["company_specific_component_6m"] = (stock - sector).where(valid)
    out["external_shock_attribution_ratio"] = ratio

    labels = pd.Series("データ不足", index=out.index, dtype="object")
    labels.loc[stock.notna() & stock.ge(0)] = "下落対象外"
    labels.loc[ratio.notna() & ratio.lt(0.25)] = "企業固有要因を要確認"
    labels.loc[ratio.notna() & ratio.ge(0.25) & ratio.lt(0.50)] = "混合要因"
    labels.loc[ratio.notna() & ratio.ge(0.50) & ratio.lt(0.75)] = "外因優位"
    labels.loc[ratio.notna() & ratio.ge(0.75)] = "外因説明が強い"
    out["external_shock_attribution_label"] = labels
    return out


def walk_forward_events(
    analysis: pd.DataFrame,
    evaluations: pd.DataFrame,
    *,
    signal_symbols: Sequence[str] = DEFAULT_SIGNAL_SYMBOLS,
    horizons: Iterable[int] = STAR_OUTCOME_HORIZONS,
) -> pd.DataFrame:
    """Evaluate saved point-in-time signals against later saved analysis snapshots.

    No current/future fundamentals are replayed into an old decision.  The signal is
    the evaluation that was actually saved for that analysis date.  A new event starts
    only when a security transitions from outside to inside ``signal_symbols``.
    """
    prepared = _prepare_analysis(analysis)
    if prepared.empty or evaluations is None or evaluations.empty:
        return pd.DataFrame()
    attached = attach_daily_final_evaluations(prepared, evaluations)
    if attached.empty or "final_evaluation" not in attached.columns:
        return pd.DataFrame()
    attached["analysis_date"] = pd.to_datetime(attached["analysis_date"], errors="coerce").dt.tz_localize(None)
    attached["close"] = _numeric(attached, "close")
    if "selection_strategy" in attached.columns:
        attached = attached.loc[attached["selection_strategy"].fillna("").astype(str).eq("value_dislocation")].copy()
    if "selected_for_review" in attached.columns:
        attached = attached.loc[_bool_mask(attached["selected_for_review"], attached.index)].copy()
    assessed = attached.get("evaluation_status", pd.Series("", index=attached.index)).astype(str).isin(
        {EVALUATION_STATUS_SAME_DAY, EVALUATION_STATUS_BACKFILLED}
    )
    attached = attached.loc[assessed].copy()
    if attached.empty:
        return pd.DataFrame()

    attribution = add_external_shock_attribution(attached)
    price_groups = _price_groups(prepared)
    signal_set = {str(x) for x in signal_symbols}
    rows: list[dict] = []
    group_keys = ["code"] + (["selection_strategy"] if "selection_strategy" in attribution.columns else [])
    for _, group in attribution.sort_values(["code", "analysis_date"], kind="stable").groupby(group_keys, sort=False):
        previous_signal = False
        for _, row in group.iterrows():
            symbol = str(row.get("final_evaluation", ""))
            is_signal = symbol in signal_set
            entry = pd.to_numeric(pd.Series([row.get("close")]), errors="coerce").iloc[0]
            if is_signal and not previous_signal and pd.notna(entry) and float(entry) > 0:
                event = {
                    "analysis_date": pd.Timestamp(row["analysis_date"]).date().isoformat(),
                    "code": str(row.get("code", "")),
                    "name": row.get("name", ""),
                    "market": row.get("market", ""),
                    "sector": row.get("sector", ""),
                    "signal": symbol,
                    "entry_price": float(entry),
                    "drawdown_52w": row.get("drawdown_52w"),
                    "relative_return_6m": row.get("relative_return_6m"),
                    "external_shock_attribution_ratio": row.get("external_shock_attribution_ratio"),
                    "external_shock_attribution_label": row.get("external_shock_attribution_label", "データ不足"),
                }
                for horizon in horizons:
                    ret, actual_days = _forward_return(
                        price_groups,
                        event["code"],
                        pd.Timestamp(row["analysis_date"]),
                        float(entry),
                        int(horizon),
                    )
                    event[f"return_{horizon}d"] = ret
                    event[f"actual_days_{horizon}d"] = actual_days
                rows.append(event)
            previous_signal = is_signal
    return pd.DataFrame(rows)


def walk_forward_summary(
    events: pd.DataFrame,
    horizons: Iterable[int] = STAR_OUTCOME_HORIZONS,
) -> pd.DataFrame:
    rows: list[dict] = []
    for horizon in horizons:
        values = _numeric(events, f"return_{horizon}d").dropna() if events is not None else pd.Series(dtype=float)
        rows.append(
            {
                "期間": f"{int(horizon)}日",
                "確定件数": int(len(values)),
                "平均リターン": float(values.mean()) if len(values) else None,
                "中央値": float(values.median()) if len(values) else None,
                "プラス率": float((values > 0).mean()) if len(values) else None,
            }
        )
    return pd.DataFrame(rows)


def _peer_candidates(snapshot: pd.DataFrame, event: pd.Series, peer_count: int) -> tuple[pd.DataFrame, str]:
    if snapshot.empty:
        return snapshot, "なし"
    code = str(event.get("code", ""))
    candidates = snapshot.loc[snapshot["code"].astype(str).ne(code)].copy()
    sector = str(event.get("sector", "") or "").strip()
    if sector and "sector" in candidates.columns:
        same_sector = candidates.loc[candidates["sector"].fillna("").astype(str).eq(sector)].copy()
    else:
        same_sector = pd.DataFrame(columns=candidates.columns)
    base = same_sector if len(same_sector) >= 2 else candidates
    pool_label = "同業種"
    if len(same_sector) < 2:
        pool_label = "全市場フォールバック"
    if "selected_for_review" in base.columns:
        non_selected = base.loc[~_bool_mask(base["selected_for_review"], base.index)].copy()
        if len(non_selected) >= min(2, max(1, int(peer_count))):
            base = non_selected
            pool_label += "・非選択"
    if base.empty:
        return base, pool_label

    distance = pd.Series(0.0, index=base.index)
    used = 0
    for metric in PEER_DISTANCE_METRICS:
        if metric not in base.columns:
            continue
        event_value = pd.to_numeric(pd.Series([event.get(metric)]), errors="coerce").iloc[0]
        values = pd.to_numeric(base[metric], errors="coerce")
        if pd.isna(event_value) or values.notna().sum() < 2:
            continue
        scale = float(values.std())
        if not np.isfinite(scale) or scale <= 1e-9:
            scale = max(float(values.abs().median()), 0.01)
        distance = distance + (values - float(event_value)).abs().fillna(scale * 2) / scale
        used += 1
    if "market" in base.columns and str(event.get("market", "")).strip():
        distance = distance + (~base["market"].fillna("").astype(str).eq(str(event.get("market")))).astype(float) * 0.5
    base["_distance"] = distance / max(used, 1)
    return base.sort_values("_distance", kind="stable").head(max(1, int(peer_count))).copy(), pool_label


def matched_peer_event_comparison(
    analysis: pd.DataFrame,
    events: pd.DataFrame,
    *,
    peer_count: int = 5,
    horizons: Iterable[int] = STAR_OUTCOME_HORIZONS,
) -> pd.DataFrame:
    """Compare each signal with similar non-selected peers from the same saved snapshot."""
    prepared = _prepare_analysis(analysis)
    if prepared.empty or events is None or events.empty:
        return pd.DataFrame()
    price_groups = _price_groups(prepared)
    by_date = {
        pd.Timestamp(day): group.copy()
        for day, group in prepared.groupby("analysis_date", sort=False)
    }
    rows: list[dict] = []
    for _, event in events.iterrows():
        start = pd.to_datetime(event.get("analysis_date"), errors="coerce")
        if pd.isna(start):
            continue
        snapshot = by_date.get(pd.Timestamp(start))
        if snapshot is None or snapshot.empty:
            continue
        peers, pool_label = _peer_candidates(snapshot, event, peer_count)
        row = event.to_dict()
        row["peer_pool"] = pool_label
        row["peer_codes"] = ",".join(peers.get("code", pd.Series(dtype=str)).astype(str).tolist())
        row["peer_count"] = int(len(peers))
        for horizon in horizons:
            peer_returns: list[float] = []
            for _, peer in peers.iterrows():
                peer_entry = pd.to_numeric(pd.Series([peer.get("close")]), errors="coerce").iloc[0]
                if pd.isna(peer_entry) or float(peer_entry) <= 0:
                    continue
                ret, _ = _forward_return(price_groups, str(peer.get("code", "")), pd.Timestamp(start), float(peer_entry), int(horizon))
                if ret is not None and np.isfinite(ret):
                    peer_returns.append(float(ret))
            signal_return = pd.to_numeric(pd.Series([event.get(f"return_{horizon}d")]), errors="coerce").iloc[0]
            peer_mean = float(np.mean(peer_returns)) if peer_returns else None
            row[f"peer_return_{horizon}d"] = peer_mean
            row[f"peer_completed_{horizon}d"] = int(len(peer_returns))
            row[f"selection_alpha_{horizon}d"] = (
                float(signal_return - peer_mean)
                if pd.notna(signal_return) and peer_mean is not None
                else None
            )
        rows.append(row)
    return pd.DataFrame(rows)


def matched_peer_summary(
    comparison: pd.DataFrame,
    horizons: Iterable[int] = STAR_OUTCOME_HORIZONS,
) -> pd.DataFrame:
    rows: list[dict] = []
    for horizon in horizons:
        signal = _numeric(comparison, f"return_{horizon}d")
        peers = _numeric(comparison, f"peer_return_{horizon}d")
        alpha = _numeric(comparison, f"selection_alpha_{horizon}d")
        valid = signal.notna() & peers.notna() & alpha.notna()
        rows.append(
            {
                "期間": f"{int(horizon)}日",
                "比較可能イベント": int(valid.sum()),
                "シグナル平均": float(signal.loc[valid].mean()) if valid.any() else None,
                "類似非選択平均": float(peers.loc[valid].mean()) if valid.any() else None,
                "選択効果": float(alpha.loc[valid].mean()) if valid.any() else None,
                "類似銘柄超過率": float((alpha.loc[valid] > 0).mean()) if valid.any() else None,
            }
        )
    return pd.DataFrame(rows)


def latest_external_shock_attribution(analysis: pd.DataFrame, *, selected_only: bool = True) -> pd.DataFrame:
    prepared = _prepare_analysis(analysis)
    if prepared.empty:
        return pd.DataFrame()
    latest = prepared["analysis_date"].max()
    current = prepared.loc[prepared["analysis_date"].eq(latest)].copy()
    if selected_only and "selected_for_review" in current.columns:
        current = current.loc[_bool_mask(current["selected_for_review"], current.index)].copy()
    current = add_external_shock_attribution(current)
    columns = [
        "analysis_date", "code", "name", "sector", "return_6m", "relative_return_6m",
        "sector_relative_return_6m", "benchmark_return_6m_est", "sector_return_6m_est",
        "company_specific_component_6m", "external_shock_attribution_ratio",
        "external_shock_attribution_label",
    ]
    return current[[c for c in columns if c in current.columns]].sort_values(
        "external_shock_attribution_ratio", ascending=False, na_position="last"
    )
