from __future__ import annotations

import math

import numpy as np
import pandas as pd


TRADING_DAYS_6M = 126
TRADING_DAYS_52W = 252


def _safe_cagr(first: float, last: float, years: int) -> float:
    if years <= 0 or first <= 0 or last <= 0:
        return np.nan
    return (last / first) ** (1 / years) - 1


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def price_features(prices: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Build per-security price features without inventing a benchmark.

    TOPIX-relative performance is only populated when at least two valid TOPIX
    observations exist in the six-month window.  When TOPIX is unavailable the
    relative value remains NaN; the security's own return must never be used as
    a substitute because that changes the meaning of the metric.
    """
    p = prices.loc[prices["date"] <= as_of].sort_values(["code", "date"]).copy()
    rows: list[dict] = []
    for code, g in p.groupby("code", sort=False):
        if len(g) < 30:
            continue
        g = g.tail(TRADING_DAYS_52W)
        last = g.iloc[-1]
        close = float(last["close"])
        high_52w = float(g["high"].max())
        drawdown_52w = close / high_52w - 1 if high_52w > 0 else np.nan
        g6 = g.tail(TRADING_DAYS_6M)
        return_6m = close / float(g6.iloc[0]["close"]) - 1 if len(g6) >= 2 else np.nan

        topix_available = False
        topix_return_6m = np.nan
        topix_relative_return_6m = np.nan
        proxy_available = False
        proxy_return_6m = np.nan
        proxy_relative_return_6m = np.nan
        proxy_code = ""
        proxy_label = ""
        relative_return_6m = np.nan
        benchmark_available = False
        benchmark_source = "none"
        benchmark_label = "市場比較なし"
        if "topix_close" in g6.columns and g6["topix_close"].notna().sum() >= 2:
            t = g6.dropna(subset=["topix_close"])
            first_topix = float(t.iloc[0]["topix_close"])
            last_topix = float(t.iloc[-1]["topix_close"])
            if first_topix > 0:
                topix_return_6m = last_topix / first_topix - 1
                if not pd.isna(return_6m):
                    topix_relative_return_6m = return_6m - topix_return_6m
                    relative_return_6m = topix_relative_return_6m
                    topix_available = True
                    benchmark_available = True
                    benchmark_source = "official_topix"
                    benchmark_label = "正式TOPIX"

        if "topix_proxy_close" in g6.columns and g6["topix_proxy_close"].notna().sum() >= 2:
            t = g6.dropna(subset=["topix_proxy_close"])
            first_proxy = float(t.iloc[0]["topix_proxy_close"])
            last_proxy = float(t.iloc[-1]["topix_proxy_close"])
            if first_proxy > 0:
                proxy_return_6m = last_proxy / first_proxy - 1
                if not pd.isna(return_6m):
                    proxy_relative_return_6m = return_6m - proxy_return_6m
                    proxy_available = True
                    proxy_code = str(t.iloc[-1].get("topix_proxy_code", ""))
                    proxy_label = str(t.iloc[-1].get("topix_proxy_label", "TOPIX連動ETF"))
                    if not topix_available:
                        relative_return_6m = proxy_relative_return_6m
                        benchmark_available = True
                        benchmark_source = "topix_etf_proxy"
                        benchmark_label = proxy_label

        returns = g["close"].pct_change().dropna().tail(60)
        volatility_60d = float(returns.std() * math.sqrt(252)) if len(returns) >= 20 else np.nan
        recent20 = g.tail(20).copy()
        close20 = pd.to_numeric(recent20["close"], errors="coerce")
        high20 = pd.to_numeric(recent20["high"], errors="coerce")
        low20 = pd.to_numeric(recent20["low"], errors="coerce")
        valid_close = close20.where(close20 > 0)
        intraday_ranges = (high20 - low20) / valid_close
        average_intraday_range_20d = float(intraday_ranges.replace([np.inf, -np.inf], np.nan).mean())
        abs_returns20 = g["close"].pct_change().abs().tail(20)
        average_absolute_return_20d = float(abs_returns20.mean()) if abs_returns20.notna().any() else np.nan
        if "turnover_yen" in g.columns:
            turnover = pd.to_numeric(g.tail(20)["turnover_yen"], errors="coerce").mean()
        else:
            turnover = (g.tail(20)["close"] * g.tail(20)["volume"]).mean()
        rows.append(
            {
                "code": code,
                "as_of": pd.Timestamp(last["date"]),
                "close": close,
                "drawdown_52w": drawdown_52w,
                "return_6m": return_6m,
                "topix_return_6m": topix_return_6m,
                "topix_relative_return_6m": topix_relative_return_6m,
                "topix_available": topix_available,
                "topix_proxy_return_6m": proxy_return_6m,
                "topix_proxy_relative_return_6m": proxy_relative_return_6m,
                "topix_proxy_available": proxy_available,
                "topix_proxy_code": proxy_code,
                "topix_proxy_label": proxy_label,
                "relative_return_6m": relative_return_6m,
                "benchmark_available": benchmark_available,
                "benchmark_source": benchmark_source,
                "benchmark_label": benchmark_label,
                "volatility_60d": volatility_60d,
                "average_intraday_range_20d": average_intraday_range_20d,
                "average_absolute_return_20d": average_absolute_return_20d,
                "average_turnover_yen_20d": float(turnover),
            }
        )
    return pd.DataFrame(rows)


def financial_features(financials: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    f = financials.loc[financials["disclosure_date"] <= as_of].copy()
    if f.empty:
        return pd.DataFrame(columns=["code"])
    f = f.sort_values(["code", "disclosure_date"])
    rows: list[dict] = []

    for code, all_rows in f.groupby("code", sort=False):
        all_rows = all_rows.sort_values("disclosure_date")
        latest_snapshot = all_rows.iloc[-1]

        if "is_full_year_actual" in all_rows.columns:
            annual = all_rows.loc[all_rows["is_full_year_actual"].fillna(False)].copy()
            annual = annual.dropna(subset=["fiscal_year"])
            annual = annual.sort_values(["fiscal_year", "disclosure_date"])
            annual = annual.drop_duplicates("fiscal_year", keep="last").tail(3)
        else:
            annual = all_rows.sort_values(["fiscal_year", "disclosure_date"])
            annual = annual.drop_duplicates("fiscal_year", keep="last").tail(3)

        if annual.empty:
            continue
        latest_actual = annual.iloc[-1]
        sales_cagr_3y = (
            _safe_cagr(_num(annual.iloc[0]["sales"]), _num(latest_actual["sales"]), len(annual) - 1)
            if len(annual) >= 2
            else np.nan
        )
        latest_sales = _num(latest_actual.get("sales"))
        latest_op = _num(latest_actual.get("operating_profit"))
        op_margin = latest_op / latest_sales if latest_sales and latest_sales > 0 else np.nan

        op_values = pd.to_numeric(annual["operating_profit"], errors="coerce")
        operating_profit_cagr_3y = (
            _safe_cagr(float(op_values.iloc[0]), float(op_values.iloc[-1]), len(annual) - 1)
            if len(annual) >= 2 and op_values.notna().all()
            else np.nan
        )
        ocf = pd.to_numeric(annual.get("operating_cf"), errors="coerce")
        valid_conversion = op_values.notna() & ocf.notna() & (op_values > 0)
        conversion_profit = float(op_values.loc[valid_conversion].sum()) if valid_conversion.any() else np.nan
        cash_conversion_ratio_3y = (
            float(ocf.loc[valid_conversion].sum()) / conversion_profit
            if valid_conversion.any() and conversion_profit > 0
            else np.nan
        )
        ocf_positive_ratio = float((ocf > 0).mean()) if ocf.notna().any() else np.nan
        ocf_observed_years = int(ocf.notna().sum())
        ocf_positive_years = int((ocf > 0).sum()) if ocf.notna().any() else 0

        total_assets = _num(latest_snapshot.get("total_assets"))
        equity = _num(latest_snapshot.get("equity"))
        equity_ratio = equity / total_assets if total_assets and total_assets > 0 else np.nan
        cash = _num(latest_snapshot.get("cash"))
        debt = _num(latest_snapshot.get("interest_bearing_debt"))
        net_cash = cash - debt if not pd.isna(cash) and not pd.isna(debt) else np.nan
        net_cash_to_assets = (
            net_cash / total_assets
            if not pd.isna(net_cash) and total_assets and total_assets > 0
            else np.nan
        )

        forecast_rows = all_rows.dropna(subset=["forecast_operating_profit"])
        forecast_row = forecast_rows.iloc[-1] if not forecast_rows.empty else latest_snapshot
        forecast_op = _num(forecast_row.get("forecast_operating_profit"))
        forecast_op_growth = (
            forecast_op / latest_op - 1
            if latest_op and latest_op > 0 and not pd.isna(forecast_op)
            else np.nan
        )
        forecast_revision_rate = np.nan
        forecast_revision_observed = False
        revision_flag = str(forecast_row.get("is_revision", "")).strip().lower() in {
            "true", "1", "yes"
        }
        if revision_flag and len(forecast_rows) >= 2:
            previous_forecast = _num(forecast_rows.iloc[-2].get("forecast_operating_profit"))
            if previous_forecast and previous_forecast > 0 and not pd.isna(forecast_op):
                forecast_revision_rate = forecast_op / previous_forecast - 1
                forecast_revision_observed = True

        eps = _num(latest_actual.get("eps"))
        bps = _num(latest_snapshot.get("book_value_per_share"))

        def latest_non_null(column: str) -> tuple[float, object]:
            if column not in all_rows.columns:
                return np.nan, pd.NaT
            candidates = all_rows.loc[pd.to_numeric(all_rows[column], errors="coerce").notna()]
            if candidates.empty:
                return np.nan, pd.NaT
            selected = candidates.iloc[-1]
            return _num(selected.get(column)), selected.get("disclosure_date", pd.NaT)

        actual_dividend, actual_dividend_date = latest_non_null("actual_annual_dividend_per_share")
        next_dividend, next_dividend_date = latest_non_null("next_forecast_annual_dividend_per_share")
        current_dividend, current_dividend_date = latest_non_null("forecast_annual_dividend_per_share")
        if not pd.isna(next_dividend):
            forecast_dividend = next_dividend
            dividend_source = "次期会社予想"
            dividend_date = next_dividend_date
            payout_ratio, _ = latest_non_null("next_forecast_payout_ratio")
        elif not pd.isna(current_dividend):
            forecast_dividend = current_dividend
            dividend_source = "会社予想"
            dividend_date = current_dividend_date
            payout_ratio, _ = latest_non_null("forecast_payout_ratio")
        else:
            forecast_dividend = actual_dividend
            dividend_source = "直近実績" if not pd.isna(actual_dividend) else "データなし"
            dividend_date = actual_dividend_date
            payout_ratio, _ = latest_non_null("actual_payout_ratio")
        dividend_change_rate = (
            forecast_dividend / actual_dividend - 1
            if actual_dividend and actual_dividend > 0 and not pd.isna(forecast_dividend)
            else np.nan
        )
        rows.append(
            {
                "code": code,
                "financial_disclosure_date": latest_snapshot["disclosure_date"],
                "latest_actual_period_end": latest_actual.get("period_end", latest_actual.get("fiscal_year")),
                "sales_cagr_3y": sales_cagr_3y,
                "operating_profit_cagr_3y": operating_profit_cagr_3y,
                "operating_margin": op_margin,
                "operating_profit_latest": latest_op,
                "cash_conversion_ratio_3y": cash_conversion_ratio_3y,
                "operating_cf_positive_ratio_3y": ocf_positive_ratio,
                "operating_cf_observed_years": ocf_observed_years,
                "operating_cf_positive_years": ocf_positive_years,
                "equity_ratio": equity_ratio,
                "net_cash": net_cash,
                "net_cash_to_assets": net_cash_to_assets,
                "eps": eps,
                "book_value_per_share": bps,
                "forecast_operating_profit": forecast_op,
                "forecast_op_growth": forecast_op_growth,
                "forecast_revision_rate": forecast_revision_rate,
                "forecast_revision_observed": forecast_revision_observed,
                "actual_annual_dividend_per_share": actual_dividend,
                "forecast_annual_dividend_per_share": forecast_dividend,
                "dividend_forecast_source": dividend_source,
                "dividend_disclosure_date": dividend_date,
                "forecast_dividend_change_rate": dividend_change_rate,
                "payout_ratio": payout_ratio,
                "dividend_data_available": not pd.isna(forecast_dividend),
                "financial_history_years": int(len(annual)),
            }
        )
    return pd.DataFrame(rows)


def latest_event_features(events: pd.DataFrame, as_of: pd.Timestamp, max_age_days: int) -> pd.DataFrame:
    e = events.loc[events["event_date"] <= as_of].copy()
    e["event_age_days"] = (as_of - e["event_date"]).dt.days
    e = e.loc[e["event_age_days"] <= max_age_days]
    if e.empty:
        return pd.DataFrame(columns=["code"])
    e["event_strength"] = (
        e["externality"].astype(float)
        * e["temporary_probability"].astype(float)
        * (0.6 + 0.4 * e["catalyst_probability"].astype(float))
    )
    e = e.sort_values(["code", "event_strength", "event_date"], ascending=[True, False, False])
    e = e.drop_duplicates("code", keep="first")
    return e[
        [
            "code",
            "event_date",
            "event_age_days",
            "category",
            "externality",
            "temporary_probability",
            "catalyst_probability",
            "evidence",
            "source_url",
            "review_status",
            "event_strength",
        ]
    ]
