from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np
import pandas as pd

from .features import financial_features, price_features
from .attribution import add_external_shock_attribution
from .scoring import add_valuation_features, score_candidates


EVENT_PLACEHOLDERS = {
    "event_date": pd.NaT,
    "category": "",
    "externality": 0.0,
    "temporary_probability": 0.0,
    "catalyst_probability": 0.0,
    "evidence": "",
    "source_url": "",
    "review_status": "pending",
}

REQUIRED_CHECK_COLUMNS = [
    "pass_market",
    "pass_liquidity",
    "pass_price",
    "pass_equity_ratio",
    "pass_operating_profit",
    "pass_ocf_history",
    "pass_sales_trend",
    "pass_operating_margin",
    "pass_drawdown",
    "pass_relative_underperformance",
    "pass_external_shock_attribution",
    "pass_forecast",
]


def _bool_series(value: bool, index: pd.Index) -> pd.Series:
    return pd.Series(value, index=index, dtype=bool)


def _numeric_series(frame: pd.DataFrame, column: str, index: pd.Index) -> pd.Series:
    """Return a numeric Series even when the optional column is absent.

    DataFrame.get(column) returns None for a missing column and pd.to_numeric(None)
    produces a scalar NaN.  Downstream benchmark selection uses .loc, so always
    normalize optional benchmark columns to an index-aligned Series.
    """
    if column not in frame.columns:
        return pd.Series(np.nan, index=index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    if isinstance(values, pd.Series):
        return values.reindex(index)
    return pd.Series(values, index=index, dtype=float)


def _join_reasons(row: pd.Series, mapping: list[tuple[str, str]], expected: bool) -> str:
    values = [text for column, text in mapping if bool(row.get(column, False)) is expected]
    return " / ".join(values)


def prepare_quantitative_universe(
    companies: pd.DataFrame,
    prices: pd.DataFrame,
    financials: pd.DataFrame,
    as_of: pd.Timestamp,
) -> pd.DataFrame:
    """Compute threshold-independent metrics once for interactive screening."""
    pf = price_features(prices, as_of)
    ff = financial_features(financials, as_of)
    merged = companies.merge(pf, on="code", how="inner").merge(ff, on="code", how="inner")
    if merged.empty:
        return merged
    # A market-relative fall can be sector-wide rather than company-specific.  Keep
    # a separate same-sector context so unusually weak company-specific performance
    # can be treated as a possible structural problem rather than a bargain signal.
    merged["sector_peer_count_6m"] = merged.groupby("sector")["return_6m"].transform("count")
    merged["sector_return_6m_median"] = merged.groupby("sector")["return_6m"].transform("median")
    merged["sector_relative_return_6m"] = merged["return_6m"] - merged["sector_return_6m_median"]
    merged.loc[merged["sector_peer_count_6m"] < 5, "sector_relative_return_6m"] = np.nan
    for key, value in EVENT_PLACEHOLDERS.items():
        merged[key] = value
    if "shares_outstanding" not in merged.columns:
        merged["shares_outstanding"] = np.nan
    merged = add_valuation_features(merged)
    scored = score_candidates(merged)
    scored["forecast_dividend_yield"] = np.where(
        (pd.to_numeric(scored.get("close"), errors="coerce") > 0)
        & pd.to_numeric(scored.get("forecast_annual_dividend_per_share"), errors="coerce").notna(),
        pd.to_numeric(scored.get("forecast_annual_dividend_per_share"), errors="coerce")
        / pd.to_numeric(scored.get("close"), errors="coerce"),
        np.nan,
    )
    scored["quantitative_score"] = scored["quantitative_score"].clip(0, 85)
    return scored


def apply_quantitative_criteria(
    prepared: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """Apply user-adjustable hard filters and add explainable audit columns."""
    if prepared.empty:
        return prepared.copy()
    scored = prepared.copy()
    u = config["universe"]
    s = config["screen"]
    index = scored.index
    selection_strategy = str(s.get("selection_strategy", "value_dislocation"))
    if selection_strategy not in {"value_dislocation", "active_trading"}:
        selection_strategy = "value_dislocation"
    scored["selection_strategy"] = selection_strategy

    scored["pass_market"] = scored["market"].isin(u["allowed_markets"])
    scored["pass_liquidity"] = (
        scored["average_turnover_yen_20d"] >= float(u["min_average_turnover_yen_20d"])
    )
    scored["pass_price"] = scored["close"] >= float(u["min_price_yen"])
    scored["pass_equity_ratio"] = scored["equity_ratio"] >= float(s["minimum_equity_ratio"])
    scored["pass_operating_profit"] = scored["operating_profit_latest"] > 0

    minimum_ocf_ratio = float(s.get("minimum_operating_cf_positive_ratio_3y", 0.0))
    if minimum_ocf_ratio <= 0:
        scored["pass_ocf_history"] = _bool_series(True, index)
    else:
        scored["pass_ocf_history"] = (
            scored["operating_cf_positive_ratio_3y"].notna()
            & (scored["operating_cf_positive_ratio_3y"] >= minimum_ocf_ratio)
        )

    minimum_sales_cagr = float(s.get("minimum_sales_cagr_3y", -1.0))
    scored["pass_sales_trend"] = (
        scored["sales_cagr_3y"].isna()
        | (scored["sales_cagr_3y"] >= minimum_sales_cagr)
    )
    if bool(s.get("require_sales_history", False)):
        scored["pass_sales_trend"] &= scored["sales_cagr_3y"].notna()

    minimum_operating_margin = float(s.get("minimum_operating_margin", 0.0))
    scored["pass_operating_margin"] = (
        scored["operating_margin"].notna()
        & (scored["operating_margin"] >= minimum_operating_margin)
    )
    scored["pass_drawdown"] = scored["drawdown_52w"] <= float(s["minimum_drawdown_52w"])

    benchmark_mode = str(s.get("market_benchmark_mode", "auto"))
    official_available = scored.get("topix_available", False)
    proxy_available = scored.get("topix_proxy_available", False)
    if not isinstance(official_available, pd.Series):
        official_available = _bool_series(False, index)
    if not isinstance(proxy_available, pd.Series):
        proxy_available = _bool_series(False, index)
    if benchmark_mode == "official_topix":
        scored["relative_return_6m"] = _numeric_series(scored, "topix_relative_return_6m", index)
        scored["benchmark_available"] = official_available.fillna(False).astype(bool)
        scored["benchmark_source"] = "official_topix"
        scored["benchmark_label"] = "正式TOPIX"
    elif benchmark_mode == "topix_etf_proxy":
        scored["relative_return_6m"] = _numeric_series(scored, "topix_proxy_relative_return_6m", index)
        scored["benchmark_available"] = proxy_available.fillna(False).astype(bool)
        scored["benchmark_source"] = "topix_etf_proxy"
        scored["benchmark_label"] = scored.get("topix_proxy_label", "TOPIX連動ETF代理値")
    elif benchmark_mode == "disabled":
        scored["relative_return_6m"] = np.nan
        scored["benchmark_available"] = False
        scored["benchmark_source"] = "disabled"
        scored["benchmark_label"] = "市場比較無効"
    else:
        use_official = official_available.fillna(False).astype(bool)
        scored["relative_return_6m"] = _numeric_series(scored, "topix_proxy_relative_return_6m", index)
        official_values = _numeric_series(scored, "topix_relative_return_6m", index)
        scored.loc[use_official, "relative_return_6m"] = official_values.loc[use_official]
        scored["benchmark_available"] = use_official | proxy_available.fillna(False).astype(bool)
        scored["benchmark_source"] = np.where(use_official, "official_topix", np.where(proxy_available.fillna(False), "topix_etf_proxy", "none"))
        proxy_labels = scored.get("topix_proxy_label", pd.Series("TOPIX連動ETF代理値", index=index)).fillna("TOPIX連動ETF代理値")
        scored["benchmark_label"] = np.where(use_official, "正式TOPIX", np.where(proxy_available.fillna(False), proxy_labels, "市場比較なし"))

    scored["benchmark_return_6m"] = np.nan
    official_mask = scored["benchmark_source"].astype(str).eq("official_topix")
    proxy_mask = scored["benchmark_source"].astype(str).eq("topix_etf_proxy")
    official_returns = _numeric_series(scored, "topix_return_6m", index)
    proxy_returns = _numeric_series(scored, "topix_proxy_return_6m", index)
    scored.loc[official_mask, "benchmark_return_6m"] = official_returns.loc[official_mask]
    scored.loc[proxy_mask, "benchmark_return_6m"] = proxy_returns.loc[proxy_mask]
    attribution_method = str(s.get("external_shock_attribution_method", "v2_sector_absolute"))
    scored = add_external_shock_attribution(scored, method=attribution_method)

    attribution_minimum = float(s.get("minimum_external_shock_attribution", 0.0))
    attribution_minimum = min(max(attribution_minimum, 0.0), 1.0)
    attribution_policy = str(s.get("external_shock_attribution_when_missing", "skip_with_warning"))
    if attribution_policy not in {"skip_with_warning", "fail"}:
        attribution_policy = "skip_with_warning"
    attribution_available = _numeric_series(scored, "external_shock_attribution", index).notna()
    # A zero threshold disables this new screen entirely, preserving the pre-B cohort.
    if attribution_minimum <= 0.0:
        attribution_pass = _bool_series(True, index)
    else:
        attribution_pass = attribution_available & (
            _numeric_series(scored, "external_shock_attribution", index) >= attribution_minimum
        )
        missing_pass = attribution_policy == "skip_with_warning"
        if missing_pass:
            attribution_pass |= ~attribution_available
    if selection_strategy == "active_trading":
        attribution_pass = _bool_series(True, index)
    scored["external_shock_attribution_minimum"] = attribution_minimum
    scored["external_shock_attribution_missing_policy"] = attribution_policy
    scored["external_shock_attribution_missing"] = ~attribution_available
    scored["external_shock_attribution_skipped"] = (
        ~attribution_available
        & attribution_pass
        & (attribution_minimum > 0.0)
        & (attribution_policy == "skip_with_warning")
        & (selection_strategy == "value_dislocation")
    )
    attribution_values = _numeric_series(scored, "external_shock_attribution", index)
    scored["external_shock_attribution_below_minimum"] = (
        (attribution_minimum > 0.0)
        & attribution_available
        & attribution_values.lt(attribution_minimum)
        & (selection_strategy == "value_dislocation")
    )
    scored["external_shock_attribution_missing_failed"] = (
        (attribution_minimum > 0.0)
        & ~attribution_available
        & (attribution_policy == "fail")
        & (selection_strategy == "value_dislocation")
    )
    scored["pass_external_shock_attribution"] = attribution_pass.astype(bool)

    relative_filter_enabled = bool(s.get("use_relative_underperformance_filter", True)) and benchmark_mode != "disabled"
    scored["relative_filter_enabled"] = relative_filter_enabled
    scored["relative_filter_applied"] = (
        relative_filter_enabled
        & scored["benchmark_available"].fillna(False).astype(bool)
    )
    relative_threshold = float(s["minimum_relative_underperformance_6m"])
    relative_pass_when_missing = str(
        s.get("relative_filter_when_topix_missing", "skip_with_warning")
    ) == "skip_with_warning"
    scored["pass_relative_underperformance"] = (
        scored["relative_filter_applied"]
        & scored["relative_return_6m"].notna()
        & (scored["relative_return_6m"] <= relative_threshold)
    )
    if not relative_filter_enabled:
        scored["pass_relative_underperformance"] = True
    elif relative_pass_when_missing:
        scored.loc[~scored["relative_filter_applied"], "pass_relative_underperformance"] = True

    require_forecast = bool(s.get("require_forecast", False))
    forecast_threshold = float(s["maximum_forecast_op_decline"])
    if require_forecast:
        scored["pass_forecast"] = (
            scored["forecast_op_growth"].notna()
            & (scored["forecast_op_growth"] >= forecast_threshold)
        )
    else:
        scored["pass_forecast"] = (
            scored["forecast_op_growth"].isna()
            | (scored["forecast_op_growth"] >= forecast_threshold)
        )

    use_structural_guard = bool(s.get("use_structural_deterioration_guard", True))
    cash_conversion = _numeric_series(scored, "cash_conversion_ratio", index)
    margin_change = _numeric_series(scored, "operating_margin_change_3y", index)
    forecast_revision = _numeric_series(scored, "forecast_revision_rate", index)
    sector_relative = _numeric_series(scored, "sector_relative_return_6m", index)
    if use_structural_guard:
        scored["pass_cash_conversion"] = cash_conversion.isna() | (
            cash_conversion >= float(s.get("minimum_cash_conversion_ratio", 0.70))
        )
        scored["pass_margin_stability"] = margin_change.isna() | (
            margin_change >= float(s.get("minimum_operating_margin_change_3y", -0.03))
        )
        scored["pass_forecast_revision"] = forecast_revision.isna() | (
            forecast_revision >= float(s.get("minimum_forecast_revision_rate", -0.10))
        )
        scored["pass_sector_relative"] = sector_relative.isna() | (
            sector_relative >= float(s.get("minimum_sector_relative_return_6m", -0.15))
        )
    else:
        for column in (
            "pass_cash_conversion", "pass_margin_stability",
            "pass_forecast_revision", "pass_sector_relative",
        ):
            scored[column] = True
    structural_columns = [
        "pass_cash_conversion", "pass_margin_stability",
        "pass_forecast_revision", "pass_sector_relative",
    ]
    scored["pass_structural_deterioration_guard"] = scored[structural_columns].all(axis=1)

    structural_labels = {
        "pass_cash_conversion": "利益の質（営業CF÷営業利益）",
        "pass_margin_stability": "営業利益率の悪化",
        "pass_forecast_revision": "会社予想の下方修正",
        "pass_sector_relative": "同業他社対比の異常な弱さ",
    }
    scored["structural_guard_failures"] = scored.apply(
        lambda row: " / ".join(
            label for column, label in structural_labels.items() if not bool(row.get(column, True))
        ),
        axis=1,
    )

    require_dividend = bool(s.get("require_dividend", False))
    dividend_available = scored.get("dividend_data_available", False)
    if not isinstance(dividend_available, pd.Series):
        dividend_available = _bool_series(False, index)
    dividend_yield = _numeric_series(scored, "forecast_dividend_yield", index)
    dividend_per_share = _numeric_series(scored, "forecast_annual_dividend_per_share", index)
    payout_ratio = _numeric_series(scored, "payout_ratio", index)
    dividend_change = _numeric_series(scored, "forecast_dividend_change_rate", index)
    scored["pass_dividend_available"] = dividend_available.fillna(False).astype(bool)
    scored["pass_min_dividend_per_share"] = dividend_per_share >= float(s.get("minimum_annual_dividend_per_share", 0.0))
    scored["pass_min_dividend_yield"] = dividend_yield >= float(s.get("minimum_forecast_dividend_yield", 0.0))
    maximum_yield = float(s.get("maximum_forecast_dividend_yield", 1.0))
    scored["pass_max_dividend_yield"] = dividend_yield <= maximum_yield
    maximum_payout = float(s.get("maximum_payout_ratio", 1.0))
    scored["pass_payout_ratio"] = payout_ratio.isna() | (payout_ratio <= maximum_payout)
    if bool(s.get("exclude_forecast_dividend_cut", False)):
        scored["pass_dividend_cut"] = dividend_change.isna() | (dividend_change >= 0)
    else:
        scored["pass_dividend_cut"] = True
    dividend_columns = [
        "pass_dividend_available", "pass_min_dividend_per_share",
        "pass_min_dividend_yield", "pass_max_dividend_yield",
        "pass_payout_ratio", "pass_dividend_cut",
    ]
    scored["pass_dividend_conditions"] = scored[dividend_columns].all(axis=1)
    if not require_dividend:
        scored["pass_dividend_conditions"] = True

    volatility = _numeric_series(scored, "volatility_60d", index)
    intraday_range = _numeric_series(scored, "average_intraday_range_20d", index)
    turnover = _numeric_series(scored, "average_turnover_yen_20d", index)
    scored["pass_daytrade_volatility"] = volatility.notna() & (
        volatility >= float(s.get("minimum_volatility_60d", 0.35))
    )
    scored["pass_daytrade_intraday_range"] = intraday_range.notna() & (
        intraday_range >= float(s.get("minimum_average_intraday_range_20d", 0.025))
    )
    # Percentile score is local to the certified snapshot; it never triggers a data fetch.
    vol_rank = volatility.rank(pct=True).fillna(0.0)
    range_rank = intraday_range.rank(pct=True).fillna(0.0)
    turnover_rank = turnover.rank(pct=True).fillna(0.0)
    scored["daytrade_activity_score"] = 100.0 * (0.45 * vol_rank + 0.35 * range_rank + 0.20 * turnover_rank)
    scored["pass_daytrade_activity_score"] = scored["daytrade_activity_score"] >= float(
        s.get("minimum_daytrade_activity_score", 50.0)
    )

    hard_columns = REQUIRED_CHECK_COLUMNS + ["pass_structural_deterioration_guard", "pass_dividend_conditions"]
    scored["hard_filter_pass"] = scored[hard_columns].all(axis=1)
    minimum_score = float(s.get("quantitative_min_score", 70))
    scored["pass_quantitative_score"] = scored["quantitative_score"] >= minimum_score
    if selection_strategy == "active_trading":
        scored["strategy_score"] = scored["daytrade_activity_score"]
        scored["selected_for_review"] = (
            scored[["pass_market", "pass_liquidity", "pass_price"]].all(axis=1)
            & scored["pass_daytrade_volatility"]
            & scored["pass_daytrade_intraday_range"]
            & scored["pass_daytrade_activity_score"]
        )
    else:
        scored["strategy_score"] = scored["quantitative_score"]
        scored["selected_for_review"] = scored["hard_filter_pass"] & scored["pass_quantitative_score"]

    pass_mapping = [
        ("pass_market", "対象市場"),
        ("pass_liquidity", "売買代金"),
        ("pass_price", "最低株価"),
        ("pass_equity_ratio", "自己資本比率"),
        ("pass_operating_profit", "営業黒字"),
        ("pass_ocf_history", "営業CF履歴"),
        ("pass_sales_trend", "売上傾向"),
        ("pass_operating_margin", "営業利益率"),
        ("pass_drawdown", "52週高値からの下落"),
        ("pass_relative_underperformance", "市場比較相対下落"),
        ("pass_external_shock_attribution", "外因説明率"),
        ("pass_forecast", "会社予想"),
        ("pass_structural_deterioration_guard", "構造悪化ガード"),
        ("pass_dividend_conditions", "配当条件"),
        ("pass_quantitative_score", "定量スコア"),
        ("pass_daytrade_volatility", "60日ボラティリティ"),
        ("pass_daytrade_intraday_range", "20日平均日中値幅"),
        ("pass_daytrade_activity_score", "値動き活発度"),
    ]
    scored["pass_reasons"] = scored.apply(
        lambda row: _join_reasons(row, pass_mapping, True), axis=1
    )
    scored["fail_reasons"] = scored.apply(
        lambda row: _join_reasons(row, pass_mapping, False), axis=1
    )

    def warnings_for(row: pd.Series) -> str:
        warnings: list[str] = []
        if not bool(row.get("relative_filter_enabled", True)):
            warnings.append("市場比較の相対下落条件は設定で無効です")
        elif not bool(row.get("relative_filter_applied", False)):
            warnings.append("正式TOPIX・ETF代理値とも利用できず相対下落条件を適用していません")
        if pd.isna(row.get("forecast_op_growth")):
            warnings.append("会社予想データなし")
        if use_structural_guard:
            if pd.isna(row.get("cash_conversion_ratio")):
                warnings.append("利益現金化率データなし")
            if pd.isna(row.get("operating_margin_change_3y")):
                warnings.append("営業利益率の推移データ不足")
            if pd.isna(row.get("forecast_revision_rate")):
                warnings.append("比較可能な会社予想修正履歴なし")
            if pd.isna(row.get("sector_relative_return_6m")):
                warnings.append("同業比較に必要な6か月株価データ不足")
            failures = str(row.get("structural_guard_failures", "") or "").strip()
            if failures:
                warnings.append(f"構造悪化ガード不通過: {failures}")
        if pd.isna(row.get("operating_cf_positive_ratio_3y")):
            warnings.append("営業CF履歴不足")
        if int(row.get("financial_history_years", 0) or 0) < 3:
            warnings.append("通期財務履歴が3年未満")
        if not bool(row.get("dividend_data_available", False)):
            warnings.append("配当データなし")
        elif pd.isna(row.get("payout_ratio")):
            warnings.append("配当性向データなし")
        if not pd.isna(row.get("forecast_dividend_change_rate")) and float(row.get("forecast_dividend_change_rate")) < 0:
            warnings.append("減配予想")
        attribution = pd.to_numeric(pd.Series([row.get("external_shock_attribution_score")]), errors="coerce").iloc[0]
        if pd.notna(attribution):
            warnings.append(f"外因説明率 {float(attribution):.0f}%（選択方式による業種・市場の価格比較。因果証明ではない）")
        elif selection_strategy == "value_dislocation" and attribution_minimum > 0.0 and attribution_policy == "skip_with_warning":
            warnings.append("外因説明率を計算できないため、この条件は通して確認事項に残しました")
        elif selection_strategy == "value_dislocation":
            warnings.append("外因説明率は市場・業種比較データ不足")
        if selection_strategy == "value_dislocation":
            warnings.append("外的要因は未確認")
        else:
            warnings.append("デイトレ候補は値動きが大きく損失も拡大しやすい")
        return " / ".join(warnings)

    scored["warning_reasons"] = scored.apply(warnings_for, axis=1)
    scored["data_limitations"] = np.select(
        [
            ~scored["relative_filter_enabled"].astype(bool),
            scored["relative_filter_applied"].astype(bool),
        ],
        [
            "市場比較条件は設定で無効 / 外的要因の一次資料確認が必要",
            "外的要因の一次資料確認が必要",
        ],
        default="市場比較不可 / 外的要因の一次資料確認が必要",
    )
    return scored


def build_quantitative_table(
    companies: pd.DataFrame,
    prices: pd.DataFrame,
    financials: pd.DataFrame,
    as_of: pd.Timestamp,
    config: dict[str, Any],
) -> pd.DataFrame:
    prepared = prepare_quantitative_universe(companies, prices, financials, as_of)
    return apply_quantitative_criteria(prepared, config)


def shortlist_from_table(table: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    if table.empty:
        return table.copy()
    maximum = int(config["screen"].get("max_review_queue", 50))
    result = table.loc[table["selected_for_review"]].copy()
    strategy = str(config.get("screen", {}).get("selection_strategy", "value_dislocation"))
    primary = "daytrade_activity_score" if strategy == "active_trading" else "quantitative_score"
    result = result.sort_values(
        [primary, "average_turnover_yen_20d"], ascending=False
    )
    return result.head(maximum).reset_index(drop=True)


def external_attribution_missing_diagnostics(table: pd.DataFrame) -> pd.DataFrame:
    """Summarize unavailable-attribution counts for the full and pre-gate cohorts."""
    reason_labels = ("6か月騰落が0以上", "比較データ不足", "業種データ不足")
    if table.empty:
        return pd.DataFrame([{
            "対象": cohort,
            "対象銘柄数": 0,
            "計算不能件数": 0,
            "計算不能割合": "—",
            **{f"{reason}件数": 0 for reason in reason_labels},
        } for cohort in ("全銘柄", "外因以外の条件を通過")])

    reasons = table.get(
        "external_shock_attribution_unavailable_reason",
        pd.Series("", index=table.index, dtype="object"),
    ).fillna("").astype(str)
    pass_columns = [
        column for column in table.columns
        if column.startswith("pass_") and column != "pass_external_shock_attribution"
    ]
    if pass_columns:
        other_conditions_pass = table[pass_columns].fillna(False).astype(bool).all(axis=1)
    else:
        other_conditions_pass = table.get(
            "selected_for_review", pd.Series(False, index=table.index)
        ).fillna(False).astype(bool)

    cohorts = (
        ("全銘柄", pd.Series(True, index=table.index)),
        ("外因以外の条件を通過", other_conditions_pass),
    )
    rows: list[dict[str, int | float | str]] = []
    for label, mask in cohorts:
        scoped_reasons = reasons.loc[mask]
        total = int(mask.sum())
        missing = int(scoped_reasons.ne("").sum())
        rows.append({
            "対象": label,
            "対象銘柄数": total,
            "計算不能件数": missing,
            "計算不能割合": f"{missing / total:.1%}" if total else "—",
            **{
                f"{reason}件数": int(scoped_reasons.eq(reason).sum())
                for reason in reason_labels
            },
        })
    return pd.DataFrame(rows)


def screening_funnel(table: pd.DataFrame) -> list[dict[str, int | str]]:
    if table.empty:
        return [{"stage": "財務・株価データが揃う銘柄", "count": 0}]
    strategy = str(table.get("selection_strategy", pd.Series(["value_dislocation"])).iloc[0])
    if strategy == "active_trading":
        stages = [
            ("価格データが揃う銘柄", []),
            ("市場・流動性・株価", ["pass_market", "pass_liquidity", "pass_price"]),
            ("60日ボラティリティ", ["pass_market", "pass_liquidity", "pass_price", "pass_daytrade_volatility"]),
            ("20日平均日中値幅", ["pass_market", "pass_liquidity", "pass_price", "pass_daytrade_volatility", "pass_daytrade_intraday_range"]),
            ("値動き活発度", ["pass_market", "pass_liquidity", "pass_price", "pass_daytrade_volatility", "pass_daytrade_intraday_range", "pass_daytrade_activity_score"]),
        ]
    else:
        stages = [
            ("財務・株価データが揃う銘柄", []),
            ("市場・流動性・株価", ["pass_market", "pass_liquidity", "pass_price"]),
            (
                "財務の必須条件",
                [
                    "pass_market", "pass_liquidity", "pass_price", "pass_equity_ratio",
                    "pass_operating_profit", "pass_ocf_history", "pass_sales_trend",
                    "pass_operating_margin",
                ],
            ),
            ("価格下落条件", REQUIRED_CHECK_COLUMNS[:-2]),
            ("外因説明率条件", REQUIRED_CHECK_COLUMNS[:-1]),
            ("会社予想条件", REQUIRED_CHECK_COLUMNS),
            ("構造悪化ガード", REQUIRED_CHECK_COLUMNS + ["pass_structural_deterioration_guard"]),
            ("配当条件", REQUIRED_CHECK_COLUMNS + ["pass_structural_deterioration_guard", "pass_dividend_conditions"]),
            ("定量スコア", REQUIRED_CHECK_COLUMNS + ["pass_structural_deterioration_guard", "pass_dividend_conditions", "pass_quantitative_score"]),
        ]
    result: list[dict[str, int | str]] = []
    for label, columns in stages:
        count = len(table) if not columns else int(table[columns].all(axis=1).sum())
        result.append({"stage": label, "count": count})
    if strategy != "active_trading":
        pass_attribution = table.get("pass_external_shock_attribution", pd.Series(True, index=table.index)).fillna(False).astype(bool)
        skipped = table.get("external_shock_attribution_skipped", pd.Series(False, index=table.index)).fillna(False).astype(bool)
        below_minimum = table.get("external_shock_attribution_below_minimum", pd.Series(False, index=table.index)).fillna(False).astype(bool)
        missing_failed = table.get("external_shock_attribution_missing_failed", (~pass_attribution & ~below_minimum)).fillna(False).astype(bool)
        result.extend([
            {"stage": "外因説明率の下限未達で外れた件数", "count": int(below_minimum.sum()), "diagnostic": True},
            {"stage": "計算不能で外れた件数", "count": int(missing_failed.sum()), "diagnostic": True},
            {"stage": "計算できずに通した件数", "count": int(skipped.sum()), "diagnostic": True},
        ])
    return result


def copy_with_screen_overrides(config: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(config)
    for section in ("universe", "screen"):
        for key, value in overrides.get(section, {}).items():
            out.setdefault(section, {})[key] = value
    return out


def external_attribution_screen_comparison(
    prepared: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    """Compare both attribution formulas on identical prepared rows."""
    rows: list[dict[str, Any]] = []
    as_of_values = pd.to_datetime(prepared.get("as_of", pd.Series(dtype="datetime64[ns]")), errors="coerce").dropna()
    as_of_label = as_of_values.max().date().isoformat() if not as_of_values.empty else "同一の集約済みスナップショット"
    for method in ("v2_sector_absolute", "v1_legacy"):
        for minimum in (0.0, 0.3, 0.5, 0.7):
            for relative_enabled in (True, False):
                variant = copy_with_screen_overrides(config, {
                    "screen": {
                        "minimum_external_shock_attribution": minimum,
                        "external_shock_attribution_method": method,
                        "use_relative_underperformance_filter": relative_enabled,
                        "minimum_relative_underperformance_6m": -0.08,
                    }
                })
                evaluated = apply_quantitative_criteria(prepared, variant)
                rows.append({
                    "基準日": as_of_label,
                    "計算方式": "新方式（業種全体）" if method == "v2_sector_absolute" else "旧方式",
                    "外因説明率下限": f"{minimum:.0%}" if minimum else "なし",
                    "TOPIX比 -8%以下": "あり" if relative_enabled else "なし",
                    "定量候補数": (
                        int(evaluated["selected_for_review"].fillna(False).astype(bool).sum())
                        if "selected_for_review" in evaluated.columns else 0
                    ),
                })
    return pd.DataFrame(rows)
