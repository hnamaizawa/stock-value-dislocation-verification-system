from __future__ import annotations

import numpy as np
import pandas as pd


def _scale(value: float, low: float, high: float, points: float, inverse: bool = False) -> float:
    if pd.isna(value):
        return 0.0
    if high == low:
        return 0.0
    x = (value - low) / (high - low)
    x = float(np.clip(x, 0.0, 1.0))
    if inverse:
        x = 1.0 - x
    return x * points


def add_valuation_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["market_cap"] = out["close"] * out["shares_outstanding"]
    out["per"] = np.where(out["eps"] > 0, out["close"] / out["eps"], np.nan)
    out["pbr"] = np.where(
        out["book_value_per_share"] > 0,
        out["close"] / out["book_value_per_share"],
        np.nan,
    )
    out["sector_per_median"] = out.groupby("sector")["per"].transform("median")
    out["sector_pbr_median"] = out.groupby("sector")["pbr"].transform("median")
    out["per_vs_sector"] = out["per"] / out["sector_per_median"]
    out["pbr_vs_sector"] = out["pbr"] / out["sector_pbr_median"]
    return out


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.assign(quality_score=pd.Series(dtype=float), valuation_score=pd.Series(dtype=float), dislocation_score=pd.Series(dtype=float), external_event_score=pd.Series(dtype=float), penalty=pd.Series(dtype=float), score=pd.Series(dtype=float), red_flags=pd.Series(dtype=str))
    rows = []
    for _, r in df.iterrows():
        quality = 0.0
        quality += _scale(r.get("sales_cagr_3y"), -0.05, 0.10, 8)
        quality += _scale(r.get("operating_margin"), 0.00, 0.15, 8)
        quality += _scale(r.get("operating_cf_positive_ratio_3y"), 0.34, 1.0, 8)
        quality += _scale(r.get("equity_ratio"), 0.20, 0.60, 8)
        quality += _scale(r.get("forecast_op_growth"), -0.15, 0.20, 8)

        valuation = 0.0
        valuation += _scale(r.get("per"), 6.0, 18.0, 5, inverse=True)
        valuation += _scale(r.get("pbr"), 0.6, 1.8, 5, inverse=True)
        valuation += _scale(r.get("per_vs_sector"), 0.55, 1.10, 5, inverse=True)
        valuation += _scale(r.get("pbr_vs_sector"), 0.55, 1.10, 5, inverse=True)

        dislocation = 0.0
        dislocation += _scale(-r.get("drawdown_52w", 0), 0.15, 0.45, 14)
        dislocation += _scale(-r.get("relative_return_6m", 0), 0.05, 0.30, 11)

        external = 0.0
        external += _scale(r.get("externality"), 0.40, 1.00, 5)
        external += _scale(r.get("temporary_probability"), 0.40, 1.00, 5)
        external += _scale(r.get("catalyst_probability"), 0.20, 1.00, 5)

        penalty = 0.0
        red_flags: list[str] = []
        if r.get("operating_profit_latest", 0) <= 0:
            penalty += 18
            red_flags.append("営業赤字")
        if pd.notna(r.get("forecast_op_growth")) and r["forecast_op_growth"] < -0.20:
            penalty += 10
            red_flags.append("会社予想の営業利益が20%以上減少")
        if pd.notna(r.get("equity_ratio")) and r["equity_ratio"] < 0.20:
            penalty += 10
            red_flags.append("自己資本比率20%未満")
        if r.get("review_status") != "approved":
            penalty += 20
            red_flags.append("外的要因の証拠が未承認")
        if not str(r.get("source_url", "")).strip():
            penalty += 8
            red_flags.append("根拠URLなし")

        total = max(0.0, min(100.0, quality + valuation + dislocation + external - penalty))
        row = r.to_dict()
        row.update(
            {
                "quality_score": round(quality, 2),
                "valuation_score": round(valuation, 2),
                "dislocation_score": round(dislocation, 2),
                "external_event_score": round(external, 2),
                "penalty": round(penalty, 2),
                "score": round(total, 2),
                "red_flags": " / ".join(red_flags),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)
