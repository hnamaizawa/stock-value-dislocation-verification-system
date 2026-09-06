from __future__ import annotations

import pandas as pd

from .criteria import build_quantitative_table, shortlist_from_table


def build_quantitative_shortlist(
    companies: pd.DataFrame,
    prices: pd.DataFrame,
    financials: pd.DataFrame,
    as_of: pd.Timestamp,
    config: dict,
) -> pd.DataFrame:
    table = build_quantitative_table(companies, prices, financials, as_of, config)
    return shortlist_from_table(table, config)


def make_external_event_review_queue(shortlist: pd.DataFrame, run_id: str, data_cutoff_at: str) -> pd.DataFrame:
    columns = [
        "run_id", "data_cutoff_at", "code", "name", "sector", "market", "close",
        "quantitative_score", "drawdown_52w", "return_6m", "topix_return_6m",
        "relative_return_6m", "relative_filter_applied", "sales_cagr_3y",
        "operating_margin", "operating_cf_positive_ratio_3y", "equity_ratio",
        "forecast_op_growth", "pass_reasons", "warning_reasons", "data_limitations",
        "event_date", "category", "externality", "temporary_probability",
        "catalyst_probability", "evidence", "source_url", "review_status", "reviewer",
        "reviewed_at", "expires_at",
    ]
    if shortlist.empty:
        return pd.DataFrame(columns=columns)
    out = shortlist.copy()
    out["run_id"] = run_id
    out["data_cutoff_at"] = data_cutoff_at
    out["event_date"] = ""
    out["category"] = ""
    out["externality"] = ""
    out["temporary_probability"] = ""
    out["catalyst_probability"] = ""
    out["evidence"] = ""
    out["source_url"] = ""
    out["review_status"] = "pending"
    out["reviewer"] = ""
    out["reviewed_at"] = ""
    out["expires_at"] = ""
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    return out[columns]
