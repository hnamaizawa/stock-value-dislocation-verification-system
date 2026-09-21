from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if old not in text:
        raise RuntimeError(f"marker not found in {path}: {old[:120]!r}")
    if text.count(old) != 1:
        raise RuntimeError(f"marker not unique in {path}: count={text.count(old)}")
    write(path, text.replace(old, new, 1))


VALIDATION_MODULE = r'''from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from value_dislocation.history import (
    STAR_OUTCOME_HORIZONS,
    EVALUATION_STATUS_BACKFILLED,
    EVALUATION_STATUS_SAME_DAY,
    attach_daily_final_evaluations,
)


DEFAULT_SIGNAL_SYMBOLS = ("◎☆",)
PEER_DISTANCE_METRICS = (
    "drawdown_52w",
    "relative_return_6m",
    "operating_margin",
    "equity_ratio",
)


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(index=frame.index, dtype=float)
    values = frame[column]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, -1]
    return pd.to_numeric(values, errors="coerce")


def _bool_mask(values, index: pd.Index) -> pd.Series:
    if isinstance(values, pd.DataFrame):
        parts = [_bool_mask(values.iloc[:, i], index) for i in range(values.shape[1])]
        if not parts:
            return pd.Series(False, index=index, dtype=bool)
        return pd.concat(parts, axis=1).any(axis=1)
    if not isinstance(values, pd.Series):
        values = pd.Series(values, index=index)
    numeric = pd.to_numeric(values, errors="coerce")
    text = values.astype("string").str.strip().str.lower()
    truthy = numeric.eq(1) | text.isin({"true", "t", "yes", "y", "on"})
    return pd.Series(truthy.fillna(False).to_numpy(dtype=bool), index=index, dtype=bool)


def _prepare_analysis(analysis: pd.DataFrame) -> pd.DataFrame:
    if analysis is None or analysis.empty:
        return pd.DataFrame()
    out = analysis.copy()
    if "code" not in out.columns or "analysis_date" not in out.columns:
        return pd.DataFrame()
    out["code"] = out["code"].astype(str)
    out["analysis_date"] = pd.to_datetime(out["analysis_date"], errors="coerce").dt.tz_localize(None)
    out["close"] = _numeric(out, "close")
    out = out.dropna(subset=["analysis_date", "code"]).sort_values(["code", "analysis_date"], kind="stable")
    return out


def _price_groups(analysis: pd.DataFrame) -> dict[str, pd.DataFrame]:
    prepared = _prepare_analysis(analysis)
    if prepared.empty:
        return {}
    prices = prepared[["code", "analysis_date", "close"]].dropna(subset=["close"]).copy()
    prices = prices.loc[prices["close"] > 0]
    prices = prices.drop_duplicates(["code", "analysis_date"], keep="last")
    return {
        str(code): group.sort_values("analysis_date", kind="stable").reset_index(drop=True)
        for code, group in prices.groupby("code", sort=False)
    }


def _forward_return(
    price_groups: dict[str, pd.DataFrame],
    code: str,
    start: pd.Timestamp,
    entry_price: float,
    horizon: int,
) -> tuple[float | None, int | None]:
    group = price_groups.get(str(code))
    if group is None or group.empty or not np.isfinite(entry_price) or entry_price <= 0:
        return None, None
    target = pd.Timestamp(start) + pd.to_timedelta(int(horizon), unit="D")
    future = group.loc[group["analysis_date"] >= target]
    if future.empty:
        return None, None
    row = future.iloc[0]
    price = float(row["close"])
    actual_days = int((pd.Timestamp(row["analysis_date"]) - pd.Timestamp(start)).days)
    return price / float(entry_price) - 1.0, actual_days


def add_external_shock_attribution(frame: pd.DataFrame) -> pd.DataFrame:
    """Decompose a six-month decline into market/sector and company-specific components.

    The calculation is deliberately conservative.  It only runs when the security's
    absolute six-month return, benchmark-relative return and sector-relative return
    were all saved at the same point in time.  Missing historical inputs stay missing;
    no benchmark or sector return is fabricated.
    """
    if frame is None or frame.empty:
        return pd.DataFrame(columns=getattr(frame, "columns", None))
    out = frame.copy()
    stock = _numeric(out, "return_6m")
    market_relative = _numeric(out, "relative_return_6m")
    sector_relative = _numeric(out, "sector_relative_return_6m")
    benchmark = stock - market_relative
    sector = stock - sector_relative
    market_decline = (-benchmark).clip(lower=0)
    sector_incremental_decline = (benchmark - sector).clip(lower=0)
    total_decline = (-stock).clip(lower=0)
    external_decline = pd.concat([total_decline, market_decline + sector_incremental_decline], axis=1).min(axis=1)
    ratio = external_decline / total_decline.where(total_decline > 0)
    valid = stock.notna() & market_relative.notna() & sector_relative.notna() & total_decline.gt(0)
    ratio = ratio.where(valid).clip(lower=0, upper=1)

    out["benchmark_return_6m_est"] = benchmark.where(valid)
    out["sector_return_6m_est"] = sector.where(valid)
    out["market_decline_component_6m"] = market_decline.where(valid)
    out["sector_decline_component_6m"] = sector_incremental_decline.where(valid)
    out["company_specific_component_6m"] = (stock - sector).where(valid)
    out["external_shock_attribution_ratio"] = ratio

    labels = pd.Series("データ不足", index=out.index, dtype="object")
    labels.loc[stock.notna() & stock.ge(0)] = "下落対象外"
    labels.loc[ratio.notna() & ratio.lt(0.25)] = "企業固有要因を要確認"
    labels.loc[ratio.notna() & ratio.ge(0.25) & ratio.lt(0.50)] = "混合要因"
    labels.loc[ratio.notna() & ratio.ge(0.50) & ratio.lt(0.75)] = "外因優位"
    labels.loc[ratio.notna() & ratio.ge(0.75)] = "外因説明が強い"
    out["external_shock_attribution_label"] = labels
    return out


def walk_forward_events(
    analysis: pd.DataFrame,
    evaluations: pd.DataFrame,
    *,
    signal_symbols: Sequence[str] = DEFAULT_SIGNAL_SYMBOLS,
    horizons: Iterable[int] = STAR_OUTCOME_HORIZONS,
) -> pd.DataFrame:
    """Evaluate saved point-in-time signals against later saved analysis snapshots.

    No current/future fundamentals are replayed into an old decision.  The signal is
    the evaluation that was actually saved for that analysis date.  A new event starts
    only when a security transitions from outside to inside ``signal_symbols``.
    """
    prepared = _prepare_analysis(analysis)
    if prepared.empty or evaluations is None or evaluations.empty:
        return pd.DataFrame()
    attached = attach_daily_final_evaluations(prepared, evaluations)
    if attached.empty or "final_evaluation" not in attached.columns:
        return pd.DataFrame()
    attached["analysis_date"] = pd.to_datetime(attached["analysis_date"], errors="coerce").dt.tz_localize(None)
    attached["close"] = _numeric(attached, "close")
    if "selection_strategy" in attached.columns:
        attached = attached.loc[attached["selection_strategy"].fillna("").astype(str).eq("value_dislocation")].copy()
    if "selected_for_review" in attached.columns:
        attached = attached.loc[_bool_mask(attached["selected_for_review"], attached.index)].copy()
    assessed = attached.get("evaluation_status", pd.Series("", index=attached.index)).astype(str).isin(
        {EVALUATION_STATUS_SAME_DAY, EVALUATION_STATUS_BACKFILLED}
    )
    attached = attached.loc[assessed].copy()
    if attached.empty:
        return pd.DataFrame()

    attribution = add_external_shock_attribution(attached)
    price_groups = _price_groups(prepared)
    signal_set = {str(x) for x in signal_symbols}
    rows: list[dict] = []
    group_keys = ["code"] + (["selection_strategy"] if "selection_strategy" in attribution.columns else [])
    for _, group in attribution.sort_values(["code", "analysis_date"], kind="stable").groupby(group_keys, sort=False):
        previous_signal = False
        for _, row in group.iterrows():
            symbol = str(row.get("final_evaluation", ""))
            is_signal = symbol in signal_set
            entry = pd.to_numeric(pd.Series([row.get("close")]), errors="coerce").iloc[0]
            if is_signal and not previous_signal and pd.notna(entry) and float(entry) > 0:
                event = {
                    "analysis_date": pd.Timestamp(row["analysis_date"]).date().isoformat(),
                    "code": str(row.get("code", "")),
                    "name": row.get("name", ""),
                    "market": row.get("market", ""),
                    "sector": row.get("sector", ""),
                    "signal": symbol,
                    "entry_price": float(entry),
                    "drawdown_52w": row.get("drawdown_52w"),
                    "relative_return_6m": row.get("relative_return_6m"),
                    "external_shock_attribution_ratio": row.get("external_shock_attribution_ratio"),
                    "external_shock_attribution_label": row.get("external_shock_attribution_label", "データ不足"),
                }
                for horizon in horizons:
                    ret, actual_days = _forward_return(
                        price_groups,
                        event["code"],
                        pd.Timestamp(row["analysis_date"]),
                        float(entry),
                        int(horizon),
                    )
                    event[f"return_{horizon}d"] = ret
                    event[f"actual_days_{horizon}d"] = actual_days
                rows.append(event)
            previous_signal = is_signal
    return pd.DataFrame(rows)


def walk_forward_summary(
    events: pd.DataFrame,
    horizons: Iterable[int] = STAR_OUTCOME_HORIZONS,
) -> pd.DataFrame:
    rows: list[dict] = []
    for horizon in horizons:
        values = _numeric(events, f"return_{horizon}d").dropna() if events is not None else pd.Series(dtype=float)
        rows.append(
            {
                "期間": f"{int(horizon)}日",
                "確定件数": int(len(values)),
                "平均リターン": float(values.mean()) if len(values) else None,
                "中央値": float(values.median()) if len(values) else None,
                "プラス率": float((values > 0).mean()) if len(values) else None,
            }
        )
    return pd.DataFrame(rows)


def _peer_candidates(snapshot: pd.DataFrame, event: pd.Series, peer_count: int) -> tuple[pd.DataFrame, str]:
    if snapshot.empty:
        return snapshot, "なし"
    code = str(event.get("code", ""))
    candidates = snapshot.loc[snapshot["code"].astype(str).ne(code)].copy()
    sector = str(event.get("sector", "") or "").strip()
    if sector and "sector" in candidates.columns:
        same_sector = candidates.loc[candidates["sector"].fillna("").astype(str).eq(sector)].copy()
    else:
        same_sector = pd.DataFrame(columns=candidates.columns)
    base = same_sector if len(same_sector) >= 2 else candidates
    pool_label = "同業種"
    if len(same_sector) < 2:
        pool_label = "全市場フォールバック"
    if "selected_for_review" in base.columns:
        non_selected = base.loc[~_bool_mask(base["selected_for_review"], base.index)].copy()
        if len(non_selected) >= min(2, max(1, int(peer_count))):
            base = non_selected
            pool_label += "・非選択"
    if base.empty:
        return base, pool_label

    distance = pd.Series(0.0, index=base.index)
    used = 0
    for metric in PEER_DISTANCE_METRICS:
        if metric not in base.columns:
            continue
        event_value = pd.to_numeric(pd.Series([event.get(metric)]), errors="coerce").iloc[0]
        values = pd.to_numeric(base[metric], errors="coerce")
        if pd.isna(event_value) or values.notna().sum() < 2:
            continue
        scale = float(values.std())
        if not np.isfinite(scale) or scale <= 1e-9:
            scale = max(float(values.abs().median()), 0.01)
        distance = distance + (values - float(event_value)).abs().fillna(scale * 2) / scale
        used += 1
    if "market" in base.columns and str(event.get("market", "")).strip():
        distance = distance + (~base["market"].fillna("").astype(str).eq(str(event.get("market")))).astype(float) * 0.5
    base["_distance"] = distance / max(used, 1)
    return base.sort_values("_distance", kind="stable").head(max(1, int(peer_count))).copy(), pool_label


def matched_peer_event_comparison(
    analysis: pd.DataFrame,
    events: pd.DataFrame,
    *,
    peer_count: int = 5,
    horizons: Iterable[int] = STAR_OUTCOME_HORIZONS,
) -> pd.DataFrame:
    """Compare each signal with similar non-selected peers from the same saved snapshot."""
    prepared = _prepare_analysis(analysis)
    if prepared.empty or events is None or events.empty:
        return pd.DataFrame()
    price_groups = _price_groups(prepared)
    by_date = {
        pd.Timestamp(day): group.copy()
        for day, group in prepared.groupby("analysis_date", sort=False)
    }
    rows: list[dict] = []
    for _, event in events.iterrows():
        start = pd.to_datetime(event.get("analysis_date"), errors="coerce")
        if pd.isna(start):
            continue
        snapshot = by_date.get(pd.Timestamp(start))
        if snapshot is None or snapshot.empty:
            continue
        peers, pool_label = _peer_candidates(snapshot, event, peer_count)
        row = event.to_dict()
        row["peer_pool"] = pool_label
        row["peer_codes"] = ",".join(peers.get("code", pd.Series(dtype=str)).astype(str).tolist())
        row["peer_count"] = int(len(peers))
        for horizon in horizons:
            peer_returns: list[float] = []
            for _, peer in peers.iterrows():
                peer_entry = pd.to_numeric(pd.Series([peer.get("close")]), errors="coerce").iloc[0]
                if pd.isna(peer_entry) or float(peer_entry) <= 0:
                    continue
                ret, _ = _forward_return(price_groups, str(peer.get("code", "")), pd.Timestamp(start), float(peer_entry), int(horizon))
                if ret is not None and np.isfinite(ret):
                    peer_returns.append(float(ret))
            signal_return = pd.to_numeric(pd.Series([event.get(f"return_{horizon}d")]), errors="coerce").iloc[0]
            peer_mean = float(np.mean(peer_returns)) if peer_returns else None
            row[f"peer_return_{horizon}d"] = peer_mean
            row[f"peer_completed_{horizon}d"] = int(len(peer_returns))
            row[f"selection_alpha_{horizon}d"] = (
                float(signal_return - peer_mean)
                if pd.notna(signal_return) and peer_mean is not None
                else None
            )
        rows.append(row)
    return pd.DataFrame(rows)


def matched_peer_summary(
    comparison: pd.DataFrame,
    horizons: Iterable[int] = STAR_OUTCOME_HORIZONS,
) -> pd.DataFrame:
    rows: list[dict] = []
    for horizon in horizons:
        signal = _numeric(comparison, f"return_{horizon}d")
        peers = _numeric(comparison, f"peer_return_{horizon}d")
        alpha = _numeric(comparison, f"selection_alpha_{horizon}d")
        valid = signal.notna() & peers.notna() & alpha.notna()
        rows.append(
            {
                "期間": f"{int(horizon)}日",
                "比較可能イベント": int(valid.sum()),
                "シグナル平均": float(signal.loc[valid].mean()) if valid.any() else None,
                "類似非選択平均": float(peers.loc[valid].mean()) if valid.any() else None,
                "選択効果": float(alpha.loc[valid].mean()) if valid.any() else None,
                "類似銘柄超過率": float((alpha.loc[valid] > 0).mean()) if valid.any() else None,
            }
        )
    return pd.DataFrame(rows)


def latest_external_shock_attribution(analysis: pd.DataFrame, *, selected_only: bool = True) -> pd.DataFrame:
    prepared = _prepare_analysis(analysis)
    if prepared.empty:
        return pd.DataFrame()
    latest = prepared["analysis_date"].max()
    current = prepared.loc[prepared["analysis_date"].eq(latest)].copy()
    if selected_only and "selected_for_review" in current.columns:
        current = current.loc[_bool_mask(current["selected_for_review"], current.index)].copy()
    current = add_external_shock_attribution(current)
    columns = [
        "analysis_date", "code", "name", "sector", "return_6m", "relative_return_6m",
        "sector_relative_return_6m", "benchmark_return_6m_est", "sector_return_6m_est",
        "company_specific_component_6m", "external_shock_attribution_ratio",
        "external_shock_attribution_label",
    ]
    return current[[c for c in columns if c in current.columns]].sort_values(
        "external_shock_attribution_ratio", ascending=False, na_position="last"
    )
'''

TEST_MODULE = r'''from __future__ import annotations

from pathlib import Path

import pandas as pd

from value_dislocation.strategy_validation import (
    add_external_shock_attribution,
    matched_peer_event_comparison,
    matched_peer_summary,
    walk_forward_events,
    walk_forward_summary,
)


def test_external_shock_attribution_decomposes_market_sector_and_company():
    frame = pd.DataFrame([{
        "code": "1000",
        "return_6m": -0.20,
        "relative_return_6m": -0.10,
        "sector_relative_return_6m": -0.05,
    }])
    out = add_external_shock_attribution(frame).iloc[0]
    assert round(float(out["benchmark_return_6m_est"]), 6) == -0.10
    assert round(float(out["sector_return_6m_est"]), 6) == -0.15
    assert round(float(out["external_shock_attribution_ratio"]), 6) == 0.75
    assert round(float(out["company_specific_component_6m"]), 6) == -0.05
    assert out["external_shock_attribution_label"] == "外因説明が強い"


def _analysis_rows():
    dates = ["2026-01-01", "2026-01-11", "2026-01-21", "2026-01-31", "2026-03-02", "2026-04-01"]
    rows = []
    prices = {
        "1000": [100, 105, 110, 112, 120, 130],
        "2000": [100, 101, 102, 103, 104, 105],
        "3000": [100, 99, 98, 97, 96, 95],
    }
    for code, values in prices.items():
        for idx, day in enumerate(dates):
            rows.append({
                "analysis_date": day,
                "data_as_of": day,
                "code": code,
                "name": code,
                "market": "Prime",
                "sector": "TEST",
                "selection_strategy": "value_dislocation",
                "selected_for_review": code == "1000",
                "close": values[idx],
                "drawdown_52w": -0.25 if code == "1000" else (-0.24 if code == "2000" else -0.28),
                "relative_return_6m": -0.12 if code == "1000" else (-0.11 if code == "2000" else -0.15),
                "operating_margin": 0.12,
                "equity_ratio": 0.50,
                "return_6m": -0.20,
                "sector_relative_return_6m": -0.05,
            })
    return pd.DataFrame(rows)


def _evaluations():
    return pd.DataFrame([
        {
            "evaluation_date": "2026-01-01",
            "code": "1000",
            "selection_strategy": "value_dislocation",
            "intuitive_symbol": "◎☆",
            "latest_price": 100.0,
            "latest_market_date": "2026-01-01",
            "latest_trend": "上昇トレンド",
            "evaluation_status": "当日評価済み",
            "unassessed_reason": "",
        },
        {
            "evaluation_date": "2026-01-11",
            "code": "1000",
            "selection_strategy": "value_dislocation",
            "intuitive_symbol": "◎☆",
            "latest_price": 105.0,
            "latest_market_date": "2026-01-11",
            "latest_trend": "上昇トレンド",
            "evaluation_status": "当日評価済み",
            "unassessed_reason": "",
        },
        {
            "evaluation_date": "2026-01-21",
            "code": "1000",
            "selection_strategy": "value_dislocation",
            "intuitive_symbol": "○",
            "latest_price": 110.0,
            "latest_market_date": "2026-01-21",
            "latest_trend": "上昇トレンド",
            "evaluation_status": "当日評価済み",
            "unassessed_reason": "",
        },
    ])


def test_walk_forward_uses_saved_signal_and_later_saved_prices_only():
    events = walk_forward_events(_analysis_rows(), _evaluations(), signal_symbols=("◎☆",), horizons=(10, 20, 30))
    assert len(events) == 1
    row = events.iloc[0]
    assert row["analysis_date"] == "2026-01-01"
    assert round(float(row["return_10d"]), 6) == 0.05
    assert round(float(row["return_20d"]), 6) == 0.10
    assert round(float(row["return_30d"]), 6) == 0.12
    summary = walk_forward_summary(events, horizons=(10, 20, 30))
    assert summary["確定件数"].tolist() == [1, 1, 1]


def test_matched_peers_prefer_nonselected_same_sector_and_measure_alpha():
    analysis = _analysis_rows()
    events = walk_forward_events(analysis, _evaluations(), signal_symbols=("◎☆",), horizons=(10, 20))
    comparison = matched_peer_event_comparison(analysis, events, peer_count=2, horizons=(10, 20))
    assert len(comparison) == 1
    row = comparison.iloc[0]
    assert set(str(row["peer_codes"]).split(",")) == {"2000", "3000"}
    assert row["peer_pool"].endswith("非選択")
    assert float(row["selection_alpha_10d"]) > 0
    summary = matched_peer_summary(comparison, horizons=(10, 20))
    assert int(summary.iloc[0]["比較可能イベント"]) == 1
    assert float(summary.iloc[0]["選択効果"]) > 0


def test_v063_dashboard_and_version_contract():
    dashboard = Path("dashboard.py").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    blueprint = Path("harness/app_blueprint.yaml").read_text(encoding="utf-8")
    assert '"戦略検証"' in dashboard
    assert "walk_forward_events" in dashboard
    assert "matched_peer_event_comparison" in dashboard
    assert "latest_external_shock_attribution" in dashboard
    assert "Version: **0.6.63**" in readme
    assert "blueprint_version: 0.6.63" in blueprint
'''

DOC = r'''# v0.6.63 Strategy Validation Intelligence

## 目的

「外的要因で株価が低迷しているが、本業は壊れておらず、将来の回復余地がある銘柄」という仮説を、条件追加だけでなく**検証可能性**から強化する。

## 1. Point-in-time Walk-Forward 検証

保存済みの日次分析履歴と、その日に実際に保存された最終評価だけをシグナルとして使う。過去日に現在の財務情報や現在の判定ロジックを差し戻して再計算しない。

- ◎☆、または ◎☆+◎ への遷移を1イベントとする。
- 10/20/30/60/90/180日後の最初の保存済み価格で将来リターンを計算する。
- 後日補完された評価も、補完処理自体が対象日より後の価格を使わない既存契約を満たしたものだけを利用する。
- 外部APIアクセスは行わない。

## 2. 類似非選択銘柄との比較

シグナル銘柄と同じ分析日のスナップショットから、原則として同業種・非選択銘柄を比較対象にする。

類似度は以下を使う。

- 52週ドローダウン
- 市場対比6か月騰落率
- 営業利益率
- 自己資本比率
- 市場区分（補助ペナルティ）

各期間で「シグナル平均」「類似非選択平均」「選択効果（alpha）」「類似銘柄超過率」を表示する。比較対象が不足する場合だけ全市場へフォールバックし、その旨を明示する。

## 3. External Shock Attribution

v0.6.63以降の日次履歴には `return_6m` も保存する。これにより同一point-in-timeスナップショットから、6か月下落を概算で以下に分解する。

- 市場全体の下落成分
- 業種が市場より弱かった追加成分
- 企業固有成分

`external_shock_attribution_ratio` は0〜1で、株価下落のうち市場・業種要因で説明できる割合の目安とする。

- 75%以上: 外因説明が強い
- 50%以上75%未満: 外因優位
- 25%以上50%未満: 混合要因
- 25%未満: 企業固有要因を要確認

旧履歴に `return_6m` が無い場合は推測せず「データ不足」とする。

## 非目標

- この検証結果だけで売買を自動化しない。
- External Shock Attribution を直ちにhard filterへ昇格しない。まず前向き実績とWalk-Forward実績で有効性を確認する。
- SBI認証・ブラウザ自動化・自動注文を追加しない。
'''

# New files
write("src/value_dislocation/strategy_validation.py", VALIDATION_MODULE)
write("tests/test_strategy_validation.py", TEST_MODULE)
write("docs/22_STRATEGY_VALIDATION_INTELLIGENCE.md", DOC)

# Persist absolute six-month return in point-in-time analysis history for future attribution.
replace_once(
    "src/value_dislocation/history.py",
    '    "close", "drawdown_52w", "relative_return_6m", "sector_relative_return_6m",\n',
    '    "close", "drawdown_52w", "return_6m", "relative_return_6m", "sector_relative_return_6m",\n',
)

# Dashboard imports.
replace_once(
    "dashboard.py",
    'from value_dislocation.hypothesis_invalidation import (\n',
    'from value_dislocation.strategy_validation import (\n'
    '    latest_external_shock_attribution,\n'
    '    matched_peer_event_comparison,\n'
    '    matched_peer_summary,\n'
    '    walk_forward_events,\n'
    '    walk_forward_summary,\n'
    ')\n'
    'from value_dislocation.hypothesis_invalidation import (\n',
)

STRATEGY_RENDERER = r'''

def _render_strategy_validation(evaluation: pd.DataFrame) -> None:
    """Render point-in-time strategy validation without any external data fetch."""
    analysis_signature = _analysis_history_signature(None, None)
    analysis = _cached_load_analysis_history(str(ROOT), "", "", False, analysis_signature)
    if analysis.empty:
        st.info("戦略検証に必要な日次分析履歴がまだありません。データ更新と候補分析を継続すると蓄積されます。")
        return

    st.subheader("戦略検証（Point-in-time）")
    st.caption(
        "保存済みの日次スナップショットと当時の評価だけを使います。現在の財務情報を過去へ差し戻さず、Yahoo/J-Quantsへの追加アクセスも行いません。"
    )
    signal_mode = st.segmented_control(
        "検証するシグナル",
        ["◎☆のみ", "◎☆+◎"],
        default="◎☆のみ",
        key="strategy_validation_signal_mode",
    )
    symbols = ("◎☆",) if signal_mode == "◎☆のみ" else ("◎☆", "◎")
    events = walk_forward_events(analysis, evaluation, signal_symbols=symbols)
    summary = walk_forward_summary(events)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Walk-Forwardイベント", f"{len(events):,}")
    for idx, horizon in enumerate((20, 60, 90), start=1):
        row = summary.loc[summary["期間"].eq(f"{horizon}日")]
        if row.empty or int(row.iloc[0]["確定件数"]) == 0:
            metric_cols[idx].metric(f"{horizon}日", "未確定")
        else:
            r = row.iloc[0]
            metric_cols[idx].metric(
                f"{horizon}日",
                f"{float(r['平均リターン'])*100:.1f}%",
                f"プラス率 {float(r['プラス率'])*100:.0f}% / {int(r['確定件数'])}件",
            )

    if events.empty:
        st.info("対象シグナルへの遷移イベントがまだありません。今後の履歴蓄積で自動的に検証可能になります。")
    else:
        show_summary = summary.copy()
        for col in ["平均リターン", "中央値", "プラス率"]:
            if col in show_summary.columns:
                show_summary[col] = pd.to_numeric(show_summary[col], errors="coerce") * 100
        st.markdown("#### 1. Walk-Forward実績")
        st.dataframe(show_summary, width="stretch", hide_index=True)
        st.caption("平均リターン・中央値・プラス率は%表示です。各期間の最初の保存済み観測日を使うため、休場日や未実行日はactual_daysが期間より長くなる場合があります。")
        matured = show_summary.loc[show_summary["確定件数"] > 0, ["期間", "平均リターン"]]
        if not matured.empty:
            st.bar_chart(matured.set_index("期間"), width="stretch")

        comparison = matched_peer_event_comparison(analysis, events, peer_count=5)
        peer_summary = matched_peer_summary(comparison)
        st.markdown("#### 2. 類似非選択銘柄との比較")
        if peer_summary.empty or int(peer_summary["比較可能イベント"].sum()) == 0:
            st.info("同一時点の類似非選択銘柄と将来価格がまだ不足しています。")
        else:
            peer_show = peer_summary.copy()
            for col in ["シグナル平均", "類似非選択平均", "選択効果", "類似銘柄超過率"]:
                peer_show[col] = pd.to_numeric(peer_show[col], errors="coerce") * 100
            st.dataframe(peer_show, width="stretch", hide_index=True)
            peer_chart = peer_show.loc[peer_show["比較可能イベント"] > 0, ["期間", "選択効果"]]
            if not peer_chart.empty:
                st.caption("選択効果 = シグナル銘柄のリターン − 類似非選択銘柄平均。プラスなら銘柄選択自体に付加価値があった可能性があります。")
                st.bar_chart(peer_chart.set_index("期間"), width="stretch")

    st.markdown("#### 3. External Shock Attribution（外因説明率）")
    attribution = latest_external_shock_attribution(analysis, selected_only=True)
    if attribution.empty:
        st.info("最新候補の外因説明率を計算できる履歴がありません。")
        return
    ratios = pd.to_numeric(attribution.get("external_shock_attribution_ratio"), errors="coerce").dropna()
    a1, a2, a3 = st.columns(3)
    a1.metric("計算可能銘柄", f"{len(ratios):,}")
    a2.metric("平均外因説明率", f"{ratios.mean()*100:.1f}%" if len(ratios) else "データ不足")
    a3.metric("外因優位(50%以上)", f"{int((ratios >= 0.50).sum()):,}" if len(ratios) else "0")
    attribution_show = attribution.copy()
    pct_cols = [
        "return_6m", "relative_return_6m", "sector_relative_return_6m",
        "benchmark_return_6m_est", "sector_return_6m_est", "company_specific_component_6m",
        "external_shock_attribution_ratio",
    ]
    for col in pct_cols:
        if col in attribution_show.columns:
            attribution_show[col] = pd.to_numeric(attribution_show[col], errors="coerce") * 100
    st.dataframe(attribution_show, width="stretch", hide_index=True)
    st.caption(
        "外因説明率は市場・業種の下落で説明できる割合の目安です。v0.6.63より前の日次履歴にreturn_6mが無い場合は推測せずデータ不足とします。現時点ではhard filterには使いません。"
    )
'''

replace_once(
    "dashboard.py",
    '\ndef render_history_and_validation() -> None:\n',
    STRATEGY_RENDERER + '\n\ndef render_history_and_validation() -> None:\n',
)
replace_once(
    "dashboard.py",
    '        ["日次分析履歴", "評価履歴", "◎☆実績検証"],\n',
    '        ["日次分析履歴", "評価履歴", "◎☆実績検証", "戦略検証"],\n',
)
replace_once(
    "dashboard.py",
    '    elif section == "評価履歴":\n        _render_history_evaluations(evaluation)\n    else:\n        _render_history_star_validation(evaluation)\n',
    '    elif section == "評価履歴":\n        _render_history_evaluations(evaluation)\n    elif section == "◎☆実績検証":\n        _render_history_star_validation(evaluation)\n    else:\n        _render_strategy_validation(evaluation)\n',
)

# Version files.
replace_once("pyproject.toml", 'version = "0.6.62"', 'version = "0.6.63"')
replace_once("src/value_dislocation/__init__.py", '__version__ = "0.6.62"', '__version__ = "0.6.63"')
replace_once("harness/app_blueprint.yaml", "blueprint_version: 0.6.62", "blueprint_version: 0.6.63")

# Blueprint capabilities/invariants/files.
replace_once(
    "harness/app_blueprint.yaml",
    "- structural_deterioration_value_trap_guard\n",
    "- structural_deterioration_value_trap_guard\n- point_in_time_walk_forward_validation\n- matched_nonselected_peer_benchmark\n- external_shock_attribution\n",
)
replace_once(
    "harness/app_blueprint.yaml",
    "- missing_structural_guard_metric_must_warn_not_fabricate_failure\n",
    "- missing_structural_guard_metric_must_warn_not_fabricate_failure\n- strategy_validation_must_use_saved_point_in_time_history\n- strategy_validation_must_not_fetch_market_data\n- matched_peer_comparison_must_exclude_signal_security\n- missing_external_attribution_inputs_must_not_be_fabricated\n",
)
replace_once(
    "harness/app_blueprint.yaml",
    "- docs/21_STRUCTURAL_DETERIORATION_GUARDS.md\n",
    "- docs/21_STRUCTURAL_DETERIORATION_GUARDS.md\n- docs/22_STRATEGY_VALIDATION_INTELLIGENCE.md\n- src/value_dislocation/strategy_validation.py\n",
)

# Harness check.
HARNESS_CHECK = r'''

def check_strategy_validation_intelligence(root: Path) -> CheckResult:
    module_path = root / "src/value_dislocation/strategy_validation.py"
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    text = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
    required = [
        "walk_forward_events",
        "matched_peer_event_comparison",
        "external_shock_attribution_ratio",
        "attach_daily_final_evaluations",
        "target = pd.Timestamp(start) + pd.to_timedelta",
        'candidates = snapshot.loc[snapshot["code"].astype(str).ne(code)]',
    ]
    forbidden = ["yfinance", "requests.get", "fetch_yahoo", "get_eq_bars_daily", "jquants_api_client"]
    missing = [term for term in required if term not in text]
    forbidden_found = [term for term in forbidden if term in text.lower()]
    dashboard_missing = [term for term in ["戦略検証", "Walk-Forward実績", "External Shock Attribution"] if term not in dashboard]
    passed = module_path.exists() and not missing and not forbidden_found and not dashboard_missing
    return CheckResult(
        "strategy_validation_intelligence",
        passed,
        json.dumps({
            "missing": missing,
            "forbidden_network_terms": forbidden_found,
            "dashboard_missing": dashboard_missing,
        }, ensure_ascii=False),
    )
'''
replace_once(
    "scripts/harness_check.py",
    '\ndef check_dividend_screening(root: Path) -> CheckResult:\n',
    HARNESS_CHECK + '\n\ndef check_dividend_screening(root: Path) -> CheckResult:\n',
)
replace_once(
    "scripts/harness_check.py",
    '        check_large_data_navigation_performance(root),\n        check_dividend_screening(root),\n',
    '        check_large_data_navigation_performance(root),\n        check_strategy_validation_intelligence(root),\n        check_dividend_screening(root),\n',
)
replace_once(
    "scripts/harness_check.py",
    '    "src/value_dislocation/history.py",\n',
    '    "src/value_dislocation/history.py",\n    "src/value_dislocation/strategy_validation.py",\n    "docs/22_STRATEGY_VALIDATION_INTELLIGENCE.md",\n',
)

# README and changelog.
replace_once("README.md", "Version: **0.6.62**", "Version: **0.6.63**")
README_SECTION = r'''### v0.6.63 戦略検証インテリジェンス

- 保存済みpoint-in-time履歴と当時の評価だけを使うWalk-Forward検証を追加し、◎☆（または◎☆+◎）の10/20/30/60/90/180日後実績を未来情報なしで確認できるようにしました。
- 同一分析日の同業種・非選択銘柄から類似銘柄を選び、「シグナル平均 − 類似非選択平均」を選択効果として検証します。
- 6か月下落を市場・業種・企業固有に分解するExternal Shock Attribution（外因説明率）を追加しました。旧履歴に必要データが無い場合は推測せずデータ不足とします。
- 「履歴・実績検証」に「戦略検証」画面を追加しました。検証機能はローカル履歴のみを使い、Yahoo/J-Quantsへの追加アクセスを発生させません。
- External Shock Attributionは現時点ではhard filterにせず、実績を蓄積してから採否を判断します。

'''
replace_once(
    "README.md",
    "## 開発履歴（新しい順）\n\n> README の開発履歴は必ずこのセクションの先頭へ新しいバージョンを追加します。詳細な変更履歴は `CHANGELOG.md` を正本とします。\n\n",
    "## 開発履歴（新しい順）\n\n> README の開発履歴は必ずこのセクションの先頭へ新しいバージョンを追加します。詳細な変更履歴は `CHANGELOG.md` を正本とします。\n\n" + README_SECTION,
)
CHANGELOG_SECTION = r'''## v0.6.63
- 保存済みpoint-in-time日次履歴と当時評価によるWalk-Forward検証を追加。
- 同業種・非選択の類似銘柄とのマッチド比較を追加し、期間別の選択効果(alpha)を検証可能にした。
- `return_6m` をv0.6.63以降の日次履歴へ保存し、市場・業種・企業固有へ分解するExternal Shock Attributionを追加。
- 履歴・実績検証に「戦略検証」画面を追加。追加APIアクセスなし、旧履歴の欠損値は推測しない。

'''
write("CHANGELOG.md", CHANGELOG_SECTION + read("CHANGELOG.md"))

TASK_SECTION = r'''## v0.6.63 戦略検証インテリジェンス
- [x] Point-in-time Walk-Forward検証
- [x] 類似非選択銘柄とのマッチド比較
- [x] External Shock Attribution（外因説明率）
- [x] 履歴・実績検証「戦略検証」UI
- [x] 追加APIアクセス禁止・欠損値非推測のHarnessガード
- [x] 回帰テスト追加

'''
write("tasks/CURRENT.md", TASK_SECTION + read("tasks/CURRENT.md"))

print("v0.6.63 patch applied")
