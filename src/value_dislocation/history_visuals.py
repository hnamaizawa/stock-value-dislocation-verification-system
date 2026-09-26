from __future__ import annotations

import numpy as np
import pandas as pd

from .history import STAR_OUTCOME_HORIZONS


def condition_return_heatmap(condition_perf: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return aligned mean-return (%) and confirmed-count matrices."""
    if condition_perf is None or condition_perf.empty or "条件" not in condition_perf.columns:
        return pd.DataFrame(), pd.DataFrame()
    labels = condition_perf["条件"].fillna("").astype(str)
    returns = pd.DataFrame(index=labels)
    counts = pd.DataFrame(index=labels)
    returns.index.name = "条件"
    counts.index.name = "条件"
    for horizon in STAR_OUTCOME_HORIZONS:
        label = f"{horizon}日"
        avg = pd.to_numeric(
            condition_perf.get(f"{horizon}日平均", pd.Series(index=condition_perf.index, dtype=float)),
            errors="coerce",
        )
        count = pd.to_numeric(
            condition_perf.get(
                f"{horizon}日確定件数", pd.Series(index=condition_perf.index, dtype=float)
            ),
            errors="coerce",
        ).fillna(0)
        returns[label] = (avg * 100).to_numpy()
        counts[label] = count.to_numpy()
    returns = returns.mask(counts <= 0)
    return returns, counts.astype(int)


def condition_outcome_bubbles(condition_perf: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Build condition-level return/positive-rate/count observations for a bubble chart."""
    required = ["条件", f"{horizon}日平均", f"{horizon}日プラス率", f"{horizon}日確定件数"]
    if condition_perf is None or condition_perf.empty or not set(required).issubset(condition_perf.columns):
        return pd.DataFrame(columns=["条件", "平均リターン(%)", "プラス率(%)", "確定件数"])
    result = condition_perf[required].copy()
    result.columns = ["条件", "平均リターン(%)", "プラス率(%)", "確定件数"]
    result["平均リターン(%)"] = pd.to_numeric(result["平均リターン(%)"], errors="coerce") * 100
    result["プラス率(%)"] = pd.to_numeric(result["プラス率(%)"], errors="coerce") * 100
    result["確定件数"] = pd.to_numeric(result["確定件数"], errors="coerce").fillna(0).astype(int)
    return result.dropna(subset=["平均リターン(%)", "プラス率(%)"]).loc[
        lambda frame: frame["確定件数"] > 0
    ]


def security_return_bubbles(
    events: pd.DataFrame,
    x_horizon: int,
    y_horizon: int,
) -> pd.DataFrame:
    """Aggregate event returns by security for a two-horizon bubble chart."""
    columns = ["code", "name", f"return_{x_horizon}d", f"return_{y_horizon}d"]
    if events is None or events.empty or not set(columns).issubset(events.columns):
        return pd.DataFrame(
            columns=["code", "name", "横軸リターン(%)", "縦軸リターン(%)", "◎☆回数", "比較可能件数"]
        )
    frame = events[columns].copy()
    frame["code"] = frame["code"].astype(str)
    frame["name"] = frame["name"].fillna("").astype(str)
    x_col = f"return_{x_horizon}d"
    y_col = f"return_{y_horizon}d"
    frame[x_col] = pd.to_numeric(frame[x_col], errors="coerce")
    frame[y_col] = pd.to_numeric(frame[y_col], errors="coerce")
    total_counts = (
        frame.groupby(["code", "name"], dropna=False).size().rename("◎☆回数")
    )
    paired = frame[x_col].notna() & frame[y_col].notna()
    paired_frame = frame.loc[paired].copy()
    if paired_frame.empty:
        return pd.DataFrame(
            columns=["code", "name", "横軸リターン(%)", "縦軸リターン(%)", "◎☆回数", "比較可能件数"]
        )
    grouped = paired_frame.groupby(["code", "name"], dropna=False)
    result = grouped.agg(
        **{
            "横軸リターン(%)": (x_col, "mean"),
            "縦軸リターン(%)": (y_col, "mean"),
            "比較可能件数": ("code", "size"),
        }
    ).reset_index()
    result = result.merge(total_counts, on=["code", "name"], how="left")
    result["比較可能件数"] = result["比較可能件数"].astype(int)
    result["◎☆回数"] = result["◎☆回数"].astype(int)
    result["横軸リターン(%)"] *= 100
    result["縦軸リターン(%)"] *= 100
    result = result.replace([np.inf, -np.inf], np.nan)
    return result.dropna(subset=["横軸リターン(%)", "縦軸リターン(%)"]).loc[
        lambda frame: frame["比較可能件数"] > 0
    ]
