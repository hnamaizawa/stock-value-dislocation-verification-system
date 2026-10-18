from __future__ import annotations

import numpy as np
import pandas as pd


ATTRIBUTION_METHODS = {"v1_legacy", "v2_sector_absolute"}
DEFAULT_ATTRIBUTION_METHOD = "v2_sector_absolute"
MINIMUM_SECTOR_PEERS = 5


def add_external_shock_attribution(
    frame: pd.DataFrame,
    method: str = DEFAULT_ATTRIBUTION_METHOD,
) -> pd.DataFrame:
    """Add descriptive external-shock attribution using one named formula.

    v1_legacy sums negative market and sector-increment components. The default
    v2_sector_absolute formula uses only the absolute sector median decline. Neither
    result proves causality. Sector medians with fewer than five peers are unavailable.
    """
    if method not in ATTRIBUTION_METHODS:
        method = DEFAULT_ATTRIBUTION_METHOD
    out = frame.copy()
    index = out.index

    def num(name: str) -> pd.Series:
        if name not in out.columns:
            return pd.Series(np.nan, index=index, dtype=float)
        values = pd.to_numeric(out[name], errors="coerce")
        return values if isinstance(values, pd.Series) else pd.Series(values, index=index, dtype=float)

    stock = num("return_6m")
    sector = num("sector_return_6m_median")
    benchmark = num("benchmark_return_6m")
    peer_count = num("sector_peer_count_6m")

    out["market_return_component_6m"] = benchmark
    out["sector_incremental_component_6m"] = sector - benchmark
    out["company_specific_component_6m"] = stock - sector
    out["external_shock_attribution_method"] = method

    declining = stock.notna() & stock.lt(0)
    sector_sufficient = peer_count.ge(MINIMUM_SECTOR_PEERS)
    sector_available = sector.notna() & sector_sufficient
    if method == "v2_sector_absolute":
        valid = declining & sector_available
        total_decline = (-stock).where(declining)
        explained = (-sector).clip(lower=0).clip(upper=total_decline)
    else:
        valid = declining & sector_available & benchmark.notna()
        market_down = (-benchmark).clip(lower=0)
        sector_down = (-(sector - benchmark)).clip(lower=0)
        total_decline = (-stock).where(declining)
        explained = (market_down + sector_down).clip(lower=0).clip(upper=total_decline)

    ratio = (explained / total_decline).clip(lower=0, upper=1)
    out["external_shock_attribution"] = ratio.where(valid)
    out["external_shock_attribution_score"] = (out["external_shock_attribution"] * 100.0).where(valid)
    out["external_shock_attribution_available"] = valid

    # Keep unavailable reasons mutually exclusive for the existing diagnostics.
    unavailable_reason = pd.Series("", index=index, dtype="object")
    non_negative_return = stock.notna() & stock.ge(0)
    missing_stock_return = stock.isna()
    insufficient_sector = declining & (sector.isna() | ~sector_sufficient)
    missing_comparison_return = (
        declining & sector_available & benchmark.isna() & (method == "v1_legacy")
    )
    unavailable_reason.loc[non_negative_return] = "6か月騰落が0以上"
    unavailable_reason.loc[missing_stock_return | missing_comparison_return] = "比較データ不足"
    unavailable_reason.loc[insufficient_sector] = "業種データ不足"
    out["external_shock_attribution_unavailable_reason"] = unavailable_reason.where(~valid, "")
    return out
