from __future__ import annotations

import numpy as np
import pandas as pd


ATTRIBUTION_COLUMNS = [
    "attribution_market_return_6m",
    "attribution_sector_return_6m",
    "attribution_sector_component_6m",
    "attribution_company_component_6m",
    "external_shock_attribution_score",
]


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    if isinstance(values, pd.Series):
        return values.reindex(frame.index)
    return pd.Series(values, index=frame.index, dtype=float)


def _bool(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    values = frame[column]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, -1]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool).reindex(frame.index)
    text = values.astype("string").str.strip().str.lower()
    numeric = pd.to_numeric(values, errors="coerce")
    return (text.isin({"true", "t", "yes", "y", "on"}) | numeric.eq(1)).fillna(False)


def add_external_shock_attribution(frame: pd.DataFrame) -> pd.DataFrame:
    """Decompose six-month return into market, sector, and company-specific parts.

    The attribution is descriptive rather than causal.  It uses only data already
    present in the certified point-in-time feature frame:

    * market component: official TOPIX when available, otherwise labelled TOPIX ETF proxy
    * sector component: same-sector median return minus the market component
    * company component: security return minus the same-sector median

    ``external_shock_attribution_score`` is 0..100 and answers a narrower question:
    when the security's six-month return is negative, what share of that decline is
    also visible in the same-sector median?  A high value supports an external/sector
    explanation; a low value means the company-specific residual is large.  At least
    five sector peers are required so sparse groups never manufacture confidence.
    """
    out = frame.copy()
    if out.empty:
        for column in ATTRIBUTION_COLUMNS:
            out[column] = pd.Series(dtype=float)
        return out

    stock_return = _numeric(out, "return_6m")
    sector_return = _numeric(out, "sector_return_6m_median")
    peer_count = _numeric(out, "sector_peer_count_6m")
    official_return = _numeric(out, "topix_return_6m")
    proxy_return = _numeric(out, "topix_proxy_return_6m")
    official_available = _bool(out, "topix_available") & official_return.notna()
    proxy_available = _bool(out, "topix_proxy_available") & proxy_return.notna()

    market_return = pd.Series(np.nan, index=out.index, dtype=float)
    market_return.loc[proxy_available] = proxy_return.loc[proxy_available]
    market_return.loc[official_available] = official_return.loc[official_available]

    sector_usable = sector_return.notna() & peer_count.ge(5)
    sector_component = (sector_return - market_return).where(sector_usable & market_return.notna())
    company_component = (stock_return - sector_return).where(sector_usable & stock_return.notna())

    observed_decline = (-stock_return).clip(lower=0)
    sector_decline = (-sector_return).clip(lower=0)
    score = 100.0 * sector_decline / observed_decline.replace(0, np.nan)
    score = score.clip(lower=0, upper=100)
    score = score.where(sector_usable & stock_return.lt(0))

    out["attribution_market_return_6m"] = market_return
    out["attribution_sector_return_6m"] = sector_return.where(sector_usable)
    out["attribution_sector_component_6m"] = sector_component
    out["attribution_company_component_6m"] = company_component
    out["external_shock_attribution_score"] = score
    return out
