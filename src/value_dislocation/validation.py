from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from .history import STAR_OUTCOME_HORIZONS
from .strategy.attribution import add_external_shock_attribution
from .strategy.criteria import apply_quantitative_criteria, prepare_quantitative_universe


@dataclass(frozen=True)
class WalkForwardConfig:
    max_snapshots: int = 8
    spacing_trading_days: int = 20
    controls_per_event: int = 5
    minimum_history_trading_days: int = 60


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values if isinstance(values, pd.Series) else pd.Series(values, index=frame.index, dtype=float)


def _selected_benchmark_return(frame: pd.DataFrame) -> pd.Series:
    index = frame.index
    source = frame.get("benchmark_source", pd.Series("none", index=index)).astype(str)
    official = _numeric(frame, "topix_return_6m")
    proxy = _numeric(frame, "topix_proxy_return_6m")
    values = pd.Series(np.nan, index=index, dtype=float)
    values.loc[source.eq("official_topix")] = official.loc[source.eq("official_topix")]
    values.loc[source.eq("topix_etf_proxy")] = proxy.loc[source.eq("topix_etf_proxy")]
    return values


def with_attribution(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["benchmark_return_6m"] = _selected_benchmark_return(out)
    return add_external_shock_attribution(out)


def _walk_forward_dates(
    prices: pd.DataFrame,
    *,
    max_snapshots: int,
    spacing_trading_days: int,
    minimum_history_trading_days: int,
) -> list[pd.Timestamp]:
    if prices.empty or "date" not in prices.columns:
        return []
    dates = pd.Series(pd.to_datetime(prices["date"], errors="coerce").dropna().dt.normalize().unique()).sort_values().tolist()
    if len(dates) <= minimum_history_trading_days + 10:
        return []
    latest_usable_index = len(dates) - 11  # leave at least ~10 trading days for an observable outcome
    candidates: list[pd.Timestamp] = []
    i = latest_usable_index
    while i >= minimum_history_trading_days and len(candidates) < max_snapshots:
        candidates.append(pd.Timestamp(dates[i]))
        i -= max(int(spacing_trading_days), 1)
    return sorted(candidates)


def _price_groups(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    p = prices.copy()
    p["code"] = p["code"].astype(str)
    p["date"] = pd.to_datetime(p["date"], errors="coerce").dt.tz_localize(None)
    p["close"] = pd.to_numeric(p["close"], errors="coerce")
    p = p.dropna(subset=["date", "close"]).sort_values(["code", "date"])
    return {code: g.reset_index(drop=True) for code, g in p.groupby("code", sort=False)}


def _forward_return(
    groups: dict[str, pd.DataFrame],
    code: str,
    anchor: pd.Timestamp,
    entry_price: float,
    horizon_days: int,
) -> tuple[float | None, int | None]:
    g = groups.get(str(code))
    if g is None or g.empty or not np.isfinite(entry_price) or entry_price <= 0:
        return None, None
    target = pd.Timestamp(anchor).tz_localize(None).normalize() + pd.to_timedelta(int(horizon_days), unit="D")
    future = g.loc[g["date"].dt.normalize() >= target]
    if future.empty:
        return None, None
    row = future.iloc[0]
    price = float(row["close"])
    actual_days = int((pd.Timestamp(row["date"]).normalize() - pd.Timestamp(anchor).normalize()).days)
    return price / float(entry_price) - 1.0, actual_days


def _control_distance(pool: pd.DataFrame, target: pd.Series) -> pd.Series:
    # Match on the dimensions that materially affect expected return while keeping
    # the control independent of the final selection decision itself.
    metrics = ["market_cap", "drawdown_52w", "volatility_60d", "per_vs_sector", "pbr_vs_sector"]
    distances = pd.Series(0.0, index=pool.index, dtype=float)
    observed = pd.Series(0, index=pool.index, dtype=int)
    for column in metrics:
        target_value = pd.to_numeric(pd.Series([target.get(column)]), errors="coerce").iloc[0]
        values = _numeric(pool, column)
        if pd.isna(target_value):
            continue
        finite = values.dropna()
        if finite.empty:
            continue
        if column == "market_cap":
            values = np.log1p(values.clip(lower=0))
            target_value = float(np.log1p(max(float(target_value), 0.0)))
            finite = values.dropna()
        q1, q3 = finite.quantile([0.25, 0.75]).tolist() if len(finite) >= 4 else (finite.min(), finite.max())
        scale = float(q3 - q1)
        if not np.isfinite(scale) or scale <= 0:
            scale = float(finite.std())
        if not np.isfinite(scale) or scale <= 0:
            continue
        valid = values.notna()
        distances.loc[valid] += (values.loc[valid] - float(target_value)).abs() / scale
        observed.loc[valid] += 1
    return (distances / observed.replace(0, np.nan)).where(observed >= 2)


def matched_controls(universe: pd.DataFrame, target: pd.Series, *, count: int = 5) -> pd.DataFrame:
    if universe.empty:
        return pd.DataFrame()
    target_code = str(target.get("code", ""))
    pool = universe.loc[universe.get("code", pd.Series("", index=universe.index)).astype(str).ne(target_code)].copy()
    if "selected_for_review" in pool.columns:
        pool = pool.loc[~pool["selected_for_review"].fillna(False).astype(bool)].copy()
    sector = str(target.get("sector", ""))
    same_sector = pool.loc[pool.get("sector", pd.Series("", index=pool.index)).astype(str).eq(sector)].copy()
    if len(same_sector) >= count:
        pool = same_sector
    else:
        market = str(target.get("market", ""))
        same_market = pool.loc[pool.get("market", pd.Series("", index=pool.index)).astype(str).eq(market)].copy()
        if len(same_market) >= count:
            pool = same_market
    if pool.empty:
        return pool
    pool["match_distance"] = _control_distance(pool, target)
    pool = pool.dropna(subset=["match_distance"]).sort_values(["match_distance", "code"], kind="stable")
    return pool.head(max(int(count), 1)).copy()


def walk_forward_validation(
    companies: pd.DataFrame,
    prices: pd.DataFrame,
    financials: pd.DataFrame,
    config: dict,
    *,
    settings: WalkForwardConfig | None = None,
    horizons: Iterable[int] = STAR_OUTCOME_HORIZONS,
) -> pd.DataFrame:
    """Replay today's quantitative rule at historical as-of dates without look-ahead.

    Selection uses only rows whose price/disclosure date is on or before each replay
    date.  Future prices are joined *after* selection solely for outcome evaluation.
    The routine deliberately does not reconstruct historical external-event reviews or
    news; it validates the quantitative + structural screen only.
    """
    settings = settings or WalkForwardConfig()
    dates = _walk_forward_dates(
        prices,
        max_snapshots=settings.max_snapshots,
        spacing_trading_days=settings.spacing_trading_days,
        minimum_history_trading_days=settings.minimum_history_trading_days,
    )
    if not dates:
        return pd.DataFrame()
    groups = _price_groups(prices)
    events: list[dict] = []
    for as_of in dates:
        prepared = prepare_quantitative_universe(companies, prices, financials, as_of)
        evaluated = apply_quantitative_criteria(prepared, config)
        evaluated = with_attribution(evaluated)
        selected = evaluated.loc[evaluated.get("selected_for_review", False).fillna(False).astype(bool)].copy()
        for _, row in selected.iterrows():
            entry = float(pd.to_numeric(pd.Series([row.get("close")]), errors="coerce").iloc[0])
            controls = matched_controls(evaluated, row, count=settings.controls_per_event)
            event = {
                "selection_date": pd.Timestamp(as_of).date().isoformat(),
                "code": str(row.get("code", "")),
                "name": row.get("name", ""),
                "sector": row.get("sector", ""),
                "entry_price": entry,
                "quantitative_score": row.get("quantitative_score"),
                "external_shock_attribution": row.get("external_shock_attribution"),
                "external_shock_attribution_score": row.get("external_shock_attribution_score"),
                "company_specific_component_6m": row.get("company_specific_component_6m"),
                "control_codes": ",".join(controls.get("code", pd.Series(dtype=str)).astype(str).tolist()),
                "control_count": int(len(controls)),
            }
            for horizon in horizons:
                selected_return, actual_days = _forward_return(groups, event["code"], as_of, entry, int(horizon))
                event[f"return_{horizon}d"] = selected_return
                event[f"actual_days_{horizon}d"] = actual_days
                control_returns: list[float] = []
                for _, control in controls.iterrows():
                    c_entry = pd.to_numeric(pd.Series([control.get("close")]), errors="coerce").iloc[0]
                    if pd.isna(c_entry):
                        continue
                    c_return, _ = _forward_return(groups, str(control.get("code", "")), as_of, float(c_entry), int(horizon))
                    if c_return is not None:
                        control_returns.append(float(c_return))
                c_mean = float(np.mean(control_returns)) if control_returns else None
                event[f"control_return_{horizon}d"] = c_mean
                event[f"selection_edge_{horizon}d"] = (
                    float(selected_return) - c_mean if selected_return is not None and c_mean is not None else None
                )
                event[f"control_completed_{horizon}d"] = len(control_returns)
            events.append(event)
    return pd.DataFrame(events)


def walk_forward_summary(events: pd.DataFrame, horizons: Iterable[int] = STAR_OUTCOME_HORIZONS) -> pd.DataFrame:
    rows: list[dict] = []
    for horizon in horizons:
        selected = _numeric(events, f"return_{horizon}d").dropna()
        control = _numeric(events, f"control_return_{horizon}d").dropna()
        edge = _numeric(events, f"selection_edge_{horizon}d").dropna()
        rows.append(
            {
                "期間": f"{int(horizon)}日",
                "確定件数": int(len(selected)),
                "候補平均": float(selected.mean()) if len(selected) else None,
                "候補プラス率": float((selected > 0).mean()) if len(selected) else None,
                "類似非選択平均": float(control.mean()) if len(control) else None,
                "選択効果": float(edge.mean()) if len(edge) else None,
                "選択効果プラス率": float((edge > 0).mean()) if len(edge) else None,
            }
        )
    return pd.DataFrame(rows)


def attribution_outcome_summary(events: pd.DataFrame, *, horizon_days: int = 30) -> pd.DataFrame:
    if events.empty or "external_shock_attribution_score" not in events.columns:
        return pd.DataFrame()
    frame = events.copy()
    score = _numeric(frame, "external_shock_attribution_score")
    returns = _numeric(frame, f"return_{int(horizon_days)}d")
    frame = frame.loc[score.notna() & returns.notna()].copy()
    if frame.empty:
        return pd.DataFrame()
    frame["外因説明率帯"] = pd.cut(
        _numeric(frame, "external_shock_attribution_score"),
        bins=[-0.001, 25, 50, 75, 100.001],
        labels=["0-25%", "25-50%", "50-75%", "75-100%"],
        include_lowest=True,
    )
    frame["_return"] = _numeric(frame, f"return_{int(horizon_days)}d")
    grouped = frame.groupby("外因説明率帯", observed=True)["_return"]
    return grouped.agg(件数="count", 平均リターン="mean", プラス率=lambda s: float((s > 0).mean())).reset_index()
