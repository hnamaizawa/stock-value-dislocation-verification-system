from __future__ import annotations

import pandas as pd

from .features import financial_features, latest_event_features, price_features
from .scoring import add_valuation_features, score_candidates


def build_screen(
    companies: pd.DataFrame,
    prices: pd.DataFrame,
    financials: pd.DataFrame,
    events: pd.DataFrame,
    as_of: pd.Timestamp,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    pf = price_features(prices, as_of)
    ff = financial_features(financials, as_of)
    ef = latest_event_features(events, as_of, config["screen"]["max_event_age_days"])
    merged = companies.merge(pf, on="code", how="inner").merge(ff, on="code", how="inner")
    merged = merged.merge(ef, on="code", how="left")
    merged = add_valuation_features(merged)

    u = config["universe"]
    s = config["screen"]
    eligible = merged[
        merged["market"].isin(u["allowed_markets"])
        & (merged["average_turnover_yen_20d"] >= u["min_average_turnover_yen_20d"])
        & (merged["close"] >= u["min_price_yen"])
        & (merged["equity_ratio"] >= s["minimum_equity_ratio"])
        & (merged["forecast_op_growth"].fillna(-999) >= s["maximum_forecast_op_decline"])
        & (merged["drawdown_52w"] <= s["minimum_drawdown_52w"])
        & (merged["relative_return_6m"] <= s["minimum_relative_underperformance_6m"])
    ].copy()

    if s.get("require_approved_external_event", True):
        eligible = eligible[
            (eligible["review_status"] == "approved")
            & (eligible["externality"] >= s["minimum_externality"])
            & (eligible["temporary_probability"] >= s["minimum_temporary_probability"])
            & (eligible["catalyst_probability"] >= s["minimum_catalyst_probability"])
        ]

    scored = score_candidates(eligible)
    candidates = scored.loc[scored["score"] >= s["min_score"]].copy()
    candidates = candidates.sort_values(["score", "average_turnover_yen_20d"], ascending=False)
    candidates = candidates.head(s["max_candidates"])

    # 外的要因の証拠不足などで落ちた銘柄も確認できるよう、レビュー待ち一覧を返す。
    review_queue = merged.loc[
        (merged["drawdown_52w"] <= s["minimum_drawdown_52w"])
        & (merged["relative_return_6m"] <= s["minimum_relative_underperformance_6m"])
        & (
            merged["review_status"].isna()
            | (merged["review_status"] != "approved")
            | (merged["externality"].fillna(0) < s["minimum_externality"])
        )
    ].copy()
    return candidates.reset_index(drop=True), review_queue.reset_index(drop=True)
