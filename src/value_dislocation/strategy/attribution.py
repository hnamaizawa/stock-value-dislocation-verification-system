from __future__ import annotations

import numpy as np
import pandas as pd


def add_external_shock_attribution(frame: pd.DataFrame) -> pd.DataFrame:
    """Decompose a 6-month stock return into market/sector/company components.

    The decomposition is descriptive, not causal proof:
        stock return = market return + sector incremental return + company-specific return

    ``external_shock_attribution`` is the share of an observed stock decline that can
    be explained by *negative* market and sector components, capped to 0..1.  It is
    only calculated when the stock return, sector median and selected benchmark return
    are all available.  Missing data stays NaN and must not be treated as zero.
    """
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

    out["market_return_component_6m"] = benchmark
    out["sector_incremental_component_6m"] = sector - benchmark
    out["company_specific_component_6m"] = stock - sector

    valid = stock.notna() & sector.notna() & benchmark.notna() & stock.lt(0)
    market_down = (-benchmark).clip(lower=0)
    sector_down = (-(sector - benchmark)).clip(lower=0)
    total_decline = (-stock).where(stock < 0)
    explained = (market_down + sector_down).clip(lower=0)
    ratio = (explained / total_decline).clip(lower=0, upper=1)
    out["external_shock_attribution"] = ratio.where(valid)
    out["external_shock_attribution_score"] = (out["external_shock_attribution"] * 100.0).where(valid)
    out["external_shock_attribution_available"] = valid
    return out
