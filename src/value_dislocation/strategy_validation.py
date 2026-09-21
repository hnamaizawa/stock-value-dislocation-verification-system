from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .decision.trend import build_price_trend_snapshot
from .strategy.criteria import apply_quantitative_criteria, prepare_quantitative_universe


VALIDATION_HORIZONS = (10, 20, 30, 60, 90, 180)
MATCH_FEATURES = (
    "market_cap",
    "drawdown_52w",
    "return_6m",
    "per_vs_sector",
    "pbr_vs_sector",
    "equity_ratio",
)


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    if isinstance(values, pd.Series):
        return values.reindex(frame.index)
    return pd.Series(values, index=frame.index, dtype=float)


def _truthy(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    values = frame[column]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, -1]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(default).astype(bool)
    numeric = pd.to_numeric(values, errors="coerce")
    text = values.astype("string").str.strip().str.lower()
    result = text.isin({"true", "t", "yes", "y", "on"}) | numeric.eq(1)
    return result.fillna(default)


def reversal_confirmation_snapshot(prices: pd.DataFrame) -> dict[str, Any]:
    """Apply the v0.6.61 ◎☆ reversal confirmation to one historical price slice."""
    trend = build_price_trend_snapshot(prices)
    latest = trend.get("latest_price")
    sma20 = trend.get("sma20")
    sma50 = trend.get("sma50")
    ret20 = trend.get("return_20d")
    score = int(trend.get("trend_score", 0) or 0)
    passed = bool(
        score >= 5
        and ret20 is not None and float(ret20) >= 0
        and latest is not None and sma20 is not None and float(latest) > float(sma20)
        and bool(trend.get("sma20_rising", False))
        and sma50 is not None and float(sma20) > float(sma50)
    )
    return {
        **trend,
        "reversal_confirmed": passed,
    }


def _normalized_distance(pool: pd.DataFrame, candidate: pd.Series) -> pd.Series:
    distances = pd.Series(0.0, index=pool.index, dtype=float)
    observed = pd.Series(0, index=pool.index, dtype=int)
    for column in MATCH_FEATURES:
        if column not in pool.columns or column not in candidate.index:
            continue
        candidate_value = pd.to_numeric(pd.Series([candidate.get(column)]), errors="coerce").iloc[0]
        if pd.isna(candidate_value):
            continue
        values = pd.to_numeric(pool[column], errors="coerce")
        if column == "market_cap":
            values = np.log1p(values.clip(lower=0))
            candidate_value = float(np.log1p(max(float(candidate_value), 0.0)))
        valid = values.notna()
        if not valid.any():
            continue
        scale = float(values.loc[valid].std(ddof=0))
        if not np.isfinite(scale) or scale <= 1e-12:
            scale = max(abs(float(values.loc[valid].median())), 1.0)
        delta = ((values - float(candidate_value)) / scale) ** 2
        distances.loc[valid] += delta.loc[valid]
        observed.loc[valid] += 1
    result = distances / observed.replace(0, np.nan)
    return result.where(observed >= 2)


def match_similar_nonselected_peers(
    table: pd.DataFrame,
    candidate_code: str,
    *,
    peer_count: int = 5,
) -> pd.DataFrame:
    """Return a same-sector-first matched control group from non-selected securities."""
    if table.empty or "code" not in table.columns:
        return pd.DataFrame()
    codes = table["code"].astype(str)
    candidate_rows = table.loc[codes.eq(str(candidate_code))]
    if candidate_rows.empty:
        return pd.DataFrame()
    candidate = candidate_rows.iloc[0]
    selected = _truthy(table, "selected_for_review", default=False)
    pool = table.loc[~selected & ~codes.eq(str(candidate_code))].copy()
    for column in ("pass_market", "pass_liquidity", "pass_price"):
        if column in pool.columns:
            pool = pool.loc[_truthy(pool, column, default=False)]
    if pool.empty:
        return pool

    sector = str(candidate.get("sector", "")).strip()
    same_sector = pool.loc[pool.get("sector", pd.Series("", index=pool.index)).astype(str).eq(sector)] if sector else pd.DataFrame()
    if len(same_sector) >= max(2, min(int(peer_count), 3)):
        pool = same_sector
    else:
        market = str(candidate.get("market", "")).strip()
        if market and "market" in pool.columns:
            same_market = pool.loc[pool["market"].astype(str).eq(market)]
            if len(same_market) >= max(2, min(int(peer_count), 3)):
                pool = same_market

    pool = pool.copy()
    pool["match_distance"] = _normalized_distance(pool, candidate)
    pool = pool.dropna(subset=["match_distance"]).sort_values(
        ["match_distance", "code"], ascending=[True, True], kind="stable"
    )
    return pool.head(max(int(peer_count), 1)).reset_index(drop=True)


def _future_return(
    price_history: pd.DataFrame,
    as_of: pd.Timestamp,
    horizon_days: int,
) -> tuple[float, float]:
    if price_history is None or price_history.empty:
        return np.nan, np.nan
    frame = price_history.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["date", "close"]).sort_values("date")
    before = frame.loc[frame["date"] <= pd.Timestamp(as_of)]
    if before.empty:
        return np.nan, np.nan
    entry = before.iloc[-1]
    entry_price = float(entry["close"])
    if not np.isfinite(entry_price) or entry_price <= 0:
        return np.nan, np.nan
    target = pd.Timestamp(as_of) + pd.to_timedelta(int(horizon_days), unit="D")
    future = frame.loc[frame["date"] >= target]
    if future.empty:
        return np.nan, np.nan
    observed = future.iloc[0]
    observed_price = float(observed["close"])
    actual_days = float((pd.Timestamp(observed["date"]) - pd.Timestamp(as_of)).days)
    return observed_price / entry_price - 1.0, actual_days


def summarize_walk_forward(events: pd.DataFrame, horizons: Iterable[int] = VALIDATION_HORIZONS) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for horizon in horizons:
        candidate = _numeric(events, f"return_{int(horizon)}d").dropna()
        peer = _numeric(events, f"peer_return_{int(horizon)}d_avg")
        excess = _numeric(events, f"excess_return_{int(horizon)}d")
        comparable = pd.concat([candidate.rename("candidate"), peer.rename("peer"), excess.rename("excess")], axis=1).dropna()
        rows.append(
            {
                "期間": f"{int(horizon)}日",
                "候補確定件数": int(len(candidate)),
                "候補平均": float(candidate.mean()) if len(candidate) else np.nan,
                "候補中央値": float(candidate.median()) if len(candidate) else np.nan,
                "候補プラス率": float((candidate > 0).mean()) if len(candidate) else np.nan,
                "対照比較件数": int(len(comparable)),
                "類似非選択平均": float(comparable["peer"].mean()) if len(comparable) else np.nan,
                "選択超過平均": float(comparable["excess"].mean()) if len(comparable) else np.nan,
                "対照超過率": float((comparable["excess"] > 0).mean()) if len(comparable) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def run_walk_forward_validation(
    companies: pd.DataFrame,
    prices: pd.DataFrame,
    financials: pd.DataFrame,
    config: dict[str, Any],
    *,
    step_trading_days: int = 5,
    max_evaluation_dates: int = 20,
    event_gap_days: int = 20,
    peer_count: int = 5,
    minimum_history_observations: int = 252,
    horizons: Iterable[int] = VALIDATION_HORIZONS,
) -> dict[str, Any]:
    """Point-in-time walk-forward validation using only locally curated data.

    The historical replay intentionally excludes human external-event review and
    historical news because reconstructing them from today's information would
    introduce look-ahead bias.  It validates the reproducible layers only:
    quantitative screen + structural deterioration guard + v0.6.61 reversal check.
    """
    if prices is None or prices.empty:
        return {"events": pd.DataFrame(), "summary": summarize_walk_forward(pd.DataFrame(), horizons), "coverage": {"reason": "株価履歴なし"}}

    p = prices.copy()
    p["date"] = pd.to_datetime(p["date"], errors="coerce")
    p["close"] = pd.to_numeric(p["close"], errors="coerce")
    p = p.dropna(subset=["date", "code", "close"]).sort_values(["code", "date"])
    p["code"] = p["code"].astype(str)
    if p.empty:
        return {"events": pd.DataFrame(), "summary": summarize_walk_forward(pd.DataFrame(), horizons), "coverage": {"reason": "有効な株価履歴なし"}}

    market_dates = pd.Index(sorted(pd.to_datetime(p["date"].dropna().unique())))
    minimum_history_observations = max(int(minimum_history_observations), 30)
    if len(market_dates) < minimum_history_observations:
        coverage = {
            "reason": "厳密なWalk-Forwardに必要な過去株価が不足",
            "available_trading_dates": int(len(market_dates)),
            "minimum_history_observations": minimum_history_observations,
            "price_start": str(pd.Timestamp(market_dates.min()).date()) if len(market_dates) else "",
            "price_end": str(pd.Timestamp(market_dates.max()).date()) if len(market_dates) else "",
        }
        return {"events": pd.DataFrame(), "summary": summarize_walk_forward(pd.DataFrame(), horizons), "coverage": coverage}

    eligible_dates = list(market_dates[minimum_history_observations - 1 :])
    step = max(int(step_trading_days), 1)
    selected_dates = list(reversed(eligible_dates[::-step][: max(int(max_evaluation_dates), 1)]))
    price_groups = {str(code): group.copy() for code, group in p.groupby("code", sort=False)}
    last_event_date: dict[str, pd.Timestamp] = {}
    events: list[dict[str, Any]] = []
    total_quantitative = 0
    total_reversal = 0

    for as_of in selected_dates:
        as_of = pd.Timestamp(as_of)
        prepared = prepare_quantitative_universe(companies, p, financials, as_of)
        if prepared.empty:
            continue
        table = apply_quantitative_criteria(prepared, config)
        if table.empty:
            continue
        selected_mask = _truthy(table, "selected_for_review", default=False)
        candidates = table.loc[selected_mask].copy()
        total_quantitative += int(len(candidates))
        for _, candidate in candidates.iterrows():
            code = str(candidate.get("code", ""))
            history = price_groups.get(code)
            if history is None or history.empty:
                continue
            historical_slice = history.loc[history["date"] <= as_of]
            if len(historical_slice) < minimum_history_observations:
                continue
            reversal = reversal_confirmation_snapshot(historical_slice)
            if not bool(reversal.get("reversal_confirmed", False)):
                continue
            total_reversal += 1
            prior = last_event_date.get(code)
            if prior is not None and (as_of - prior).days < max(int(event_gap_days), 0):
                continue
            last_event_date[code] = as_of

            peers = match_similar_nonselected_peers(table, code, peer_count=peer_count)
            peer_codes = [str(x) for x in peers.get("code", pd.Series(dtype=str)).tolist()]
            event: dict[str, Any] = {
                "validation_date": as_of.date().isoformat(),
                "code": code,
                "name": candidate.get("name", ""),
                "market": candidate.get("market", ""),
                "sector": candidate.get("sector", ""),
                "entry_price": reversal.get("latest_price", candidate.get("close", np.nan)),
                "quantitative_score": candidate.get("quantitative_score", np.nan),
                "trend_score": reversal.get("trend_score", np.nan),
                "return_20d_at_entry": reversal.get("return_20d", np.nan),
                "external_shock_attribution_score": candidate.get("external_shock_attribution_score", np.nan),
                "attribution_market_return_6m": candidate.get("attribution_market_return_6m", np.nan),
                "attribution_sector_return_6m": candidate.get("attribution_sector_return_6m", np.nan),
                "attribution_sector_component_6m": candidate.get("attribution_sector_component_6m", np.nan),
                "attribution_company_component_6m": candidate.get("attribution_company_component_6m", np.nan),
                "peer_count": int(len(peer_codes)),
                "peer_codes": ",".join(peer_codes),
            }
            for horizon in horizons:
                horizon = int(horizon)
                candidate_return, actual_days = _future_return(history, as_of, horizon)
                peer_returns: list[float] = []
                for peer_code in peer_codes:
                    peer_history = price_groups.get(peer_code)
                    if peer_history is None:
                        continue
                    peer_return, _ = _future_return(peer_history, as_of, horizon)
                    if np.isfinite(peer_return):
                        peer_returns.append(float(peer_return))
                peer_average = float(np.mean(peer_returns)) if peer_returns else np.nan
                event[f"return_{horizon}d"] = candidate_return
                event[f"actual_days_{horizon}d"] = actual_days
                event[f"peer_return_{horizon}d_avg"] = peer_average
                event[f"excess_return_{horizon}d"] = (
                    float(candidate_return) - peer_average
                    if np.isfinite(candidate_return) and np.isfinite(peer_average)
                    else np.nan
                )
            events.append(event)

    event_frame = pd.DataFrame(events)
    summary = summarize_walk_forward(event_frame, horizons)
    coverage = {
        "price_start": str(pd.Timestamp(market_dates.min()).date()),
        "price_end": str(pd.Timestamp(market_dates.max()).date()),
        "available_trading_dates": int(len(market_dates)),
        "evaluation_dates": int(len(selected_dates)),
        "evaluation_start": str(pd.Timestamp(selected_dates[0]).date()) if selected_dates else "",
        "evaluation_end": str(pd.Timestamp(selected_dates[-1]).date()) if selected_dates else "",
        "minimum_history_observations": minimum_history_observations,
        "step_trading_days": step,
        "event_gap_days": int(event_gap_days),
        "peer_count_target": int(peer_count),
        "quantitative_candidate_occurrences": int(total_quantitative),
        "reversal_candidate_occurrences": int(total_reversal),
        "deduplicated_events": int(len(event_frame)),
        "scope": "定量条件＋構造悪化ガード＋反転確認。人手の外的要因レビュー/ニュースは過去再現しない",
    }
    return {"events": event_frame, "summary": summary, "coverage": coverage}
