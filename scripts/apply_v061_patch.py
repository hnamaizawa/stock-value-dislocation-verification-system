from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}: {old[:80]!r}")
    write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str) -> None:
    text = read(path)
    new, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one regex match, found {count}: {pattern[:100]!r}")
    write(path, new)


# 1) ◎☆ becomes a reversal-confirmed top badge while preserving the old qualification as metadata.
buy_path = "src/value_dislocation/decision/buy_readiness.py"
buy_text = read(buy_path)
pattern = r"def build_intuitive_signal\(readiness: dict\[str, Any\], trend_transition: dict\[str, Any\] \| None = None\) -> dict\[str, Any\]:.*?\n\ndef build_entry_price_guidance\("
replacement = '''REVERSAL_STAR_RULE_VERSION = "reversal_v1"


def build_intuitive_signal(readiness: dict[str, Any], trend_transition: dict[str, Any] | None = None) -> dict[str, Any]:
    """Map the explainable decision result to a beginner-friendly badge.

    ``legacy_star`` reproduces the pre-v0.6.61 ◎☆ qualification so outcome history
    can compare the old rule with the new rule.  The displayed ◎☆ is deliberately
    stricter: the old quality gate must pass *and* a short-term reversal must be
    confirmed by price/MA/momentum evidence.  It is still not a guarantee or order
    recommendation.
    """
    trend_transition = trend_transition or {}
    level = str(readiness.get("decision_level", "stop"))
    score = int(readiness.get("evidence_score", 0) or 0)
    escaped = bool(trend_transition.get("escaped_downtrend"))
    current_score = int(trend_transition.get("current_score", 0) or 0)
    checks = readiness.get("checks", []) or []
    core_keys = {"sales", "margin", "equity", "ocf", "forecast", "payout", "div_change", "trend"}
    core_checks = [item for item in checks if item.get("key") in core_keys]
    core_clear = bool(core_checks) and all(item.get("status") == "pass" for item in core_checks)
    has_failure = any(item.get("status") == "fail" for item in checks)

    legacy_star = bool(level == "consider" and score >= 85 and current_score >= 2 and core_clear and not has_failure)

    current = trend_transition.get("current", {}) or {}
    latest_price = _number(current.get("latest_price"))
    sma20 = _number(current.get("sma20"))
    sma50 = _number(current.get("sma50"))
    return_20d = _number(current.get("return_20d"))
    reversal_checks = {
        "trend_score_at_least_5": current_score >= 5,
        "return_20d_nonnegative": return_20d is not None and return_20d >= 0,
        "price_above_sma20": latest_price is not None and sma20 is not None and latest_price > sma20,
        "sma20_rising": bool(current.get("sma20_rising")),
        "sma20_above_sma50": sma20 is not None and sma50 is not None and sma20 > sma50,
    }
    reversal_star = bool(legacy_star and all(reversal_checks.values()))

    metadata = {
        "star": reversal_star,
        "legacy_star": legacy_star,
        "reversal_star": reversal_star,
        "star_rule_version": REVERSAL_STAR_RULE_VERSION,
        "reversal_checks": reversal_checks,
    }

    if level == "consider" and score >= 75 and (escaped or current_score >= 2):
        if reversal_star:
            return {
                "symbol": "◎☆",
                "label": "反転確認済み候補",
                "detail": (
                    "主要な財務・業績項目に明確な欠点がなく、反転確認条件（トレンドスコア5以上、"
                    "20日騰落率0%以上、株価>MA20、MA20上向き、MA20>MA50）も満たしています。"
                ),
                **metadata,
            }
        if legacy_star:
            missing = [key for key, ok in reversal_checks.items() if not ok]
            return {
                "symbol": "◎",
                "label": "買い候補（反転確認待ち）",
                "detail": "旧◎☆条件相当ですが、反転確認条件が未達です。未達: " + ", ".join(missing),
                **metadata,
            }
        return {
            "symbol": "◎",
            "label": "買い候補",
            "detail": "定量条件が比較的揃い、最新トレンドにも改善・上向きの兆候があります。",
            **metadata,
        }
    if level == "consider":
        return {
            "symbol": "○",
            "label": "条件付き候補",
            "detail": "定量条件は比較的良好ですが、最新トレンドまたは人手確認が不足しています。",
            **metadata,
        }
    if level == "research":
        return {
            "symbol": "△",
            "label": "様子見",
            "detail": "有利材料と注意材料が混在しています。追加確認または値動きの改善を待ちます。",
            **metadata,
        }
    return {
        "symbol": "×",
        "label": "見送り",
        "detail": "重要な弱点または明確な下降トレンドがあり、現時点では買いを急がない状態です。",
        **metadata,
    }


def build_entry_price_guidance('''
new_buy, count = re.subn(pattern, replacement, buy_text, count=1, flags=re.S)
if count != 1:
    raise RuntimeError(f"failed to replace build_intuitive_signal: {count}")
write(buy_path, new_buy)


# 2) Persist both old/new star eligibility and support prospective rule comparison.
history_path = "src/value_dislocation/history.py"
text = read(history_path)

# Backfilled point-in-time evaluations should record both rule results.
old_update = '''        result.update({
            "intuitive_symbol": intuitive.get("symbol", ""),
            "latest_price": current.get("latest_price"),
            "latest_market_date": latest_market_date,
            "latest_trend": transition.get("current_state", "データ不足"),
            "trend_transition": transition.get("transition_state", "判定不能"),
            "decision_note": "後日補完。評価対象日より後の株価は使用していません。 " + str(transition.get("summary", "")),
            "evaluation_status": EVALUATION_STATUS_BACKFILLED,
            "unassessed_reason": "",
        })'''
new_update = '''        result.update({
            "intuitive_symbol": intuitive.get("symbol", ""),
            "latest_price": current.get("latest_price"),
            "latest_market_date": latest_market_date,
            "latest_trend": transition.get("current_state", "データ不足"),
            "trend_transition": transition.get("transition_state", "判定不能"),
            "decision_note": "後日補完。評価対象日より後の株価は使用していません。 " + str(transition.get("summary", "")),
            "evaluation_status": EVALUATION_STATUS_BACKFILLED,
            "unassessed_reason": "",
            "legacy_star_eligible": bool(intuitive.get("legacy_star", intuitive.get("symbol") == "◎☆")),
            "reversal_star_eligible": bool(intuitive.get("reversal_star", intuitive.get("symbol") == "◎☆")),
            "star_rule_version": str(intuitive.get("star_rule_version", "reversal_v1")),
        })'''
if text.count(old_update) != 1:
    raise RuntimeError("history.py backfill result.update pattern changed")
text = text.replace(old_update, new_update, 1)

# Replace upsert so current dashboard rows preserve both star-rule outcomes without changing dashboard.py.
upsert_pattern = r"def upsert_daily_evaluations\(project_root: Path, rows: pd.DataFrame, \*, evaluation_date: date \| str, analysis_as_of: date \| str \| None = None\) -> Path:.*?\n\ndef load_evaluation_history\("
upsert_replacement = '''def upsert_daily_evaluations(project_root: Path, rows: pd.DataFrame, *, evaluation_date: date | str, analysis_as_of: date | str | None = None) -> Path:
    """Upsert the current unified-candidate evaluation once per date/code/strategy.

    Since v0.6.61 the displayed ◎☆ is reversal-confirmed.  Persist both the old
    star qualification and the new qualification so future validation can compare
    them without rewriting historical rows.
    """
    folder = history_root(project_root) / "evaluations"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "evaluations.csv.gz"
    incoming = rows.copy()
    day = pd.Timestamp(evaluation_date).date().isoformat()
    incoming["evaluation_date"] = day
    incoming["analysis_as_of"] = pd.Timestamp(analysis_as_of).date().isoformat() if analysis_as_of is not None else None
    if "raw_code" in incoming.columns:
        incoming["code"] = incoming["raw_code"].astype(str)
    elif "code" in incoming.columns:
        incoming["code"] = incoming["code"].astype(str)
    else:
        incoming["code"] = ""
    if "直感判定" in incoming.columns:
        incoming["intuitive_symbol"] = incoming["直感判定"].astype(str).str.split().str[0]
    elif "intuitive_symbol" not in incoming.columns:
        incoming["intuitive_symbol"] = ""

    # dashboard.py already stores the human-readable detail.  The marker is used
    # only to preserve whether the pre-v0.6.61 rule would have produced ◎☆.
    note_source = incoming.get("判断メモ", incoming.get("decision_note", pd.Series("", index=incoming.index)))
    if not isinstance(note_source, pd.Series):
        note_source = pd.Series(str(note_source), index=incoming.index)
    note_source = note_source.fillna("").astype(str)
    symbols = incoming["intuitive_symbol"].fillna("").astype(str)
    if "legacy_star_eligible" not in incoming.columns:
        incoming["legacy_star_eligible"] = symbols.eq("◎☆") | note_source.str.contains("旧◎☆条件相当", regex=False)
    if "reversal_star_eligible" not in incoming.columns:
        incoming["reversal_star_eligible"] = symbols.eq("◎☆")
    if "star_rule_version" not in incoming.columns:
        incoming["star_rule_version"] = "reversal_v1"

    rename = {
        "企業名": "name", "市場": "market", "最新株価": "latest_price", "最新判定": "latest_trend",
        "変化": "trend_transition", "仮説警告": "invalidation_status", "定量スコア": "strategy_score",
        "判断メモ": "decision_note",
    }
    incoming = incoming.rename(columns={k:v for k,v in rename.items() if k in incoming.columns})
    keep = [c for c in [
        "evaluation_date", "analysis_as_of", "code", "name", "market", "selection_strategy",
        "intuitive_symbol", "strategy_score", "latest_price", "latest_market_date", "latest_trend",
        "trend_transition", "invalidation_status", "decision_note", "evaluation_status",
        "unassessed_reason", "original_final_evaluation", "original_unassessed_reason", "evaluated_at", "evaluation_as_of",
        "legacy_star_eligible", "reversal_star_eligible", "star_rule_version",
    ] if c in incoming.columns]
    incoming = incoming[keep].copy()
    if path.exists():
        try:
            current = pd.read_csv(path, dtype={"code": str}, compression="gzip")
        except Exception:
            current = pd.DataFrame()
        combined = pd.concat([current, incoming], ignore_index=True, sort=False)
    else:
        combined = incoming
    keys = [c for c in ["evaluation_date", "code", "selection_strategy"] if c in combined.columns]
    if keys:
        combined = combined.drop_duplicates(keys, keep="last")
    combined = combined.sort_values([c for c in ["evaluation_date", "code"] if c in combined.columns])
    combined.to_csv(path, index=False, encoding="utf-8-sig", compression="gzip")
    combined.to_csv(folder / "evaluations.csv", index=False, encoding="utf-8-sig")
    return path


def load_evaluation_history('''
text, count = re.subn(upsert_pattern, upsert_replacement, text, count=1, flags=re.S)
if count != 1:
    raise RuntimeError(f"failed to replace upsert_daily_evaluations: {count}")

# Replace event construction/reconciliation with mode-aware versions.  Default remains
# the historically displayed symbol, so existing saved events do not disappear.
event_pattern = r"def build_star_events\(evaluations: pd.DataFrame, horizons: Iterable\[int\] = STAR_OUTCOME_HORIZONS\) -> pd.DataFrame:.*?\n\ndef enrich_star_events_with_market_histories\("
event_replacement = '''def _stored_bool(value) -> bool | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off", "", "nan", "none", "<na>"}:
        return False
    return bool(value)


def _is_star_row(row: pd.Series, star_mode: str) -> bool:
    displayed = str(row.get("intuitive_symbol", "")) == "◎☆"
    if star_mode == "displayed":
        return displayed
    if star_mode == "legacy":
        stored = _stored_bool(row.get("legacy_star_eligible"))
        return displayed if stored is None else stored
    if star_mode == "reversal":
        stored = _stored_bool(row.get("reversal_star_eligible"))
        return False if stored is None else stored
    raise ValueError(f"unknown star_mode: {star_mode}")


def build_star_events(
    evaluations: pd.DataFrame,
    horizons: Iterable[int] = STAR_OUTCOME_HORIZONS,
    *,
    star_mode: str = "displayed",
) -> pd.DataFrame:
    """Build one event per transition into the selected star rule.

    ``displayed`` preserves the historically displayed ◎☆ series. ``legacy``
    reproduces the pre-v0.6.61 quality-star qualification where recorded, while
    ``reversal`` uses the new reversal-confirmed qualification.  Old rows without
    explicit rule metadata are never guessed as reversal-confirmed.
    """
    if evaluations.empty or "intuitive_symbol" not in evaluations.columns:
        return pd.DataFrame()
    frame = evaluations.copy()
    frame["evaluation_date"] = pd.to_datetime(frame["evaluation_date"], errors="coerce")
    frame["latest_price"] = pd.to_numeric(frame.get("latest_price"), errors="coerce")
    market_dates = pd.to_datetime(frame.get("latest_market_date"), errors="coerce") if "latest_market_date" in frame.columns else pd.Series(pd.NaT, index=frame.index)
    frame["observation_date"] = market_dates.fillna(frame["evaluation_date"])
    frame = frame.dropna(subset=["evaluation_date"]).sort_values(["code", "evaluation_date"])
    events: list[dict] = []
    for code, group in frame.groupby("code", sort=False):
        g = group.sort_values("evaluation_date").reset_index(drop=True)
        prev_star = False
        for _, row in g.iterrows():
            valid_observation = pd.notna(row.get("latest_price")) and not str(row.get("latest_trend", "")).startswith(("未実施", "取得不能"))
            if not valid_observation:
                continue
            is_star = _is_star_row(row, star_mode)
            if is_star and not prev_star:
                event = row.to_dict()
                event["star_date"] = pd.Timestamp(row["observation_date"]).date().isoformat()
                event["entry_price"] = float(row["latest_price"])
                event["star_mode"] = star_mode
                for horizon in horizons:
                    target = pd.Timestamp(row["observation_date"]) + pd.to_timedelta(int(horizon), unit="D")
                    future = g.loc[(g["observation_date"] >= target) & pd.to_numeric(g["latest_price"], errors="coerce").notna()]
                    if future.empty:
                        event[f"return_{horizon}d"] = None
                        event[f"actual_days_{horizon}d"] = None
                    else:
                        f = future.iloc[0]
                        event[f"return_{horizon}d"] = float(f["latest_price"] / row["latest_price"] - 1.0)
                        event[f"actual_days_{horizon}d"] = int((pd.Timestamp(f["observation_date"]) - pd.Timestamp(row["observation_date"])).days)
                events.append(event)
            prev_star = is_star
    return pd.DataFrame(events)


def star_rule_comparison_summary(evaluations: pd.DataFrame) -> pd.DataFrame:
    """Compare old/new star rules over the period where v0.6.61 metadata exists.

    This is intentionally prospective and point-in-time safe: pre-v0.6.61 rows are
    not reverse-engineered into the new rule because their exact reversal gate state
    was not persisted.  Returns are based on saved evaluation observations and make
    no external data request.
    """
    if evaluations is None or evaluations.empty or "star_rule_version" not in evaluations.columns:
        return pd.DataFrame()
    covered = evaluations.loc[
        evaluations["star_rule_version"].fillna("").astype(str).eq("reversal_v1")
        & evaluations.get("selection_strategy", pd.Series("value_dislocation", index=evaluations.index)).fillna("").astype(str).eq("value_dislocation")
    ].copy()
    if covered.empty:
        return pd.DataFrame()
    rows = []
    for mode, label in (("legacy", "旧◎☆条件"), ("reversal", "反転確認◎☆")):
        events = build_star_events(covered, star_mode=mode)
        row = {"判定方式": label, "開始イベント数": int(len(events))}
        for horizon in STAR_OUTCOME_HORIZONS:
            values = _numeric_column(events, f"return_{horizon}d").dropna()
            row[f"{horizon}日平均"] = float(values.mean()) if len(values) else None
            row[f"{horizon}日プラス率"] = float((values > 0).mean()) if len(values) else None
            row[f"{horizon}日確定件数"] = int(len(values))
        rows.append(row)
    result = pd.DataFrame(rows)
    result.attrs["coverage_start"] = str(pd.to_datetime(covered["evaluation_date"], errors="coerce").min().date()) if pd.to_datetime(covered["evaluation_date"], errors="coerce").notna().any() else ""
    return result


def reconcile_star_outcomes(
    evaluations: pd.DataFrame,
    saved_events: pd.DataFrame | None = None,
    *,
    star_mode: str = "displayed",
) -> pd.DataFrame:
    """Rebuild the complete star event set while preserving saved forward returns."""
    comparison = star_rule_comparison_summary(evaluations)
    rebuilt = build_star_events(evaluations, star_mode=star_mode)
    if rebuilt.empty:
        rebuilt.attrs["star_rule_comparison"] = comparison
        return rebuilt
    saved = pd.DataFrame() if saved_events is None else saved_events.copy()
    if saved.empty or not {"code", "star_date"}.issubset(saved.columns):
        result = rebuilt.sort_values(["star_date", "code"], ascending=[True, True]).reset_index(drop=True)
        result.attrs["star_rule_comparison"] = comparison
        return result

    rebuilt = rebuilt.copy()
    saved = saved.copy()
    rebuilt["code"] = rebuilt["code"].astype(str)
    saved["code"] = saved["code"].astype(str)
    rebuilt["star_date"] = rebuilt["star_date"].astype(str)
    saved["star_date"] = saved["star_date"].astype(str)
    saved_by_key = saved.drop_duplicates(["code", "star_date"], keep="last").set_index(["code", "star_date"])
    preserve = ["entry_price"]
    for horizon in STAR_OUTCOME_HORIZONS:
        preserve.extend([f"return_{horizon}d", f"actual_days_{horizon}d"])
    for idx, row in rebuilt.iterrows():
        key = (str(row.get("code", "")), str(row.get("star_date", "")))
        if key not in saved_by_key.index:
            continue
        prior = saved_by_key.loc[key]
        for col in preserve:
            if col not in saved_by_key.columns:
                continue
            value = prior.get(col)
            if pd.notna(value):
                rebuilt.at[idx, col] = value
    result = rebuilt.sort_values(["star_date", "code"], ascending=[True, True]).reset_index(drop=True)
    result.attrs["star_rule_comparison"] = comparison
    return result


def enrich_star_events_with_market_histories('''
text, count = re.subn(event_pattern, event_replacement, text, count=1, flags=re.S)
if count != 1:
    raise RuntimeError(f"failed to replace star event block: {count}")

# Extend the existing analysis summary with a prospective old/new rule comparison.
summary_pattern = r"def star_validation_text_summary\(\n    events: pd.DataFrame,.*?\n    return lines\[:4\]\n"
summary_replacement = '''def star_validation_text_summary(
    events: pd.DataFrame,
    forward_summary: pd.DataFrame,
    condition_perf: pd.DataFrame | None = None,
    *,
    condition_horizon: int = 90,
) -> list[str]:
    """Build a compact non-causal summary of ◎☆ forward-return validation."""
    if events is None or events.empty:
        return ["◎☆開始イベントがまだないため、実績サマリを作成できません。"]
    codes = _summary_text_column(events, "code")
    unique_codes = int(codes.loc[codes.ne("")].nunique())
    lines = [f"◎☆開始イベントは {len(events):,} 件、対象は {unique_codes:,} 銘柄です。"]

    forward = pd.DataFrame() if forward_summary is None else forward_summary.reset_index().copy()
    if not forward.empty and {"期間", "平均リターン(%)", "確定件数"}.issubset(forward.columns):
        forward["平均リターン(%)"] = pd.to_numeric(forward["平均リターン(%)"], errors="coerce")
        forward["確定件数"] = pd.to_numeric(forward["確定件数"], errors="coerce").fillna(0)
        matured = forward.loc[(forward["確定件数"] > 0) & forward["平均リターン(%)"].notna()].copy()
        if matured.empty:
            lines.append("10〜180日の将来リターンはまだ十分に確定していません。")
        else:
            best = matured.sort_values("平均リターン(%)", ascending=False).iloc[0]
            lines.append(f"確定済み期間では {best['期間']} の平均リターンが最も高く {float(best['平均リターン(%)']):+.1f}%（{int(best['確定件数']):,}件）です。")
            positive_periods = int((matured["平均リターン(%)"] > 0).sum())
            lines.append(f"平均リターンがプラスの期間は、確定済み {len(matured):,} 期間中 {positive_periods:,} 期間です。")

    comparison = events.attrs.get("star_rule_comparison") if hasattr(events, "attrs") else None
    if isinstance(comparison, pd.DataFrame) and not comparison.empty and "判定方式" in comparison.columns:
        legacy = comparison.loc[comparison["判定方式"] == "旧◎☆条件"]
        reversal = comparison.loc[comparison["判定方式"] == "反転確認◎☆"]
        if not legacy.empty and not reversal.empty:
            l = legacy.iloc[0]
            r = reversal.iloc[0]
            coverage_start = comparison.attrs.get("coverage_start", "v0.6.61導入後")
            lines.append(
                f"新旧ルール比較（{coverage_start}以降・保存評価ベース）: 旧◎☆条件 {int(l['開始イベント数']):,} 件、反転確認◎☆ {int(r['開始イベント数']):,} 件です。"
            )
            if int(l.get("20日確定件数", 0) or 0) and int(r.get("20日確定件数", 0) or 0):
                lines.append(
                    "20日実績は旧条件 "
                    f"平均 {float(l['20日平均']) * 100:+.1f}% / プラス率 {float(l['20日プラス率']) * 100:.1f}%、"
                    "反転確認条件 "
                    f"平均 {float(r['20日平均']) * 100:+.1f}% / プラス率 {float(r['20日プラス率']) * 100:.1f}%です。"
                )
            else:
                lines.append("新旧ルールの20日比較は、反転確認◎☆の実績が確定するまで蓄積中です。")

    perf = pd.DataFrame() if condition_perf is None else condition_perf.copy()
    avg_col = f"{condition_horizon}日平均"
    count_col = f"{condition_horizon}日確定件数"
    if not perf.empty and {"条件", avg_col, count_col}.issubset(perf.columns):
        perf[avg_col] = pd.to_numeric(perf[avg_col], errors="coerce")
        perf[count_col] = pd.to_numeric(perf[count_col], errors="coerce").fillna(0)
        usable = perf.loc[(perf[count_col] > 0) & perf[avg_col].notna()].copy()
        if not usable.empty:
            best_condition = usable.sort_values(avg_col, ascending=False).iloc[0]
            lines.append(f"条件別では「{best_condition['条件']}」の{condition_horizon}日平均が最も高く {float(best_condition[avg_col]) * 100:+.1f}%（{int(best_condition[count_col]):,}件）です。因果関係ではなく参考傾向です。")
    return lines[:7]
'''
text, count = re.subn(summary_pattern, summary_replacement, text, count=1, flags=re.S)
if count != 1:
    raise RuntimeError(f"failed to replace star_validation_text_summary: {count}")
write(history_path, text)


# 3) Tests: adapt the existing star test and add explicit v0.6.61 regression coverage.
test_buy = "tests/test_buy_readiness.py"
old_transition = '''    signal = build_intuitive_signal(readiness, {"current_score": 5, "escaped_downtrend": True})
    assert signal["star"] is True
    assert signal["symbol"] == "◎☆"

    readiness["checks"] = checks + [{"key": "equity", "status": "fail"}]
    signal = build_intuitive_signal(readiness, {"current_score": 5, "escaped_downtrend": True})'''
new_transition = '''    transition = {
        "current_score": 5,
        "escaped_downtrend": True,
        "current": {
            "latest_price": 110.0,
            "sma20": 105.0,
            "sma50": 100.0,
            "sma20_rising": True,
            "return_20d": 0.04,
        },
    }
    signal = build_intuitive_signal(readiness, transition)
    assert signal["star"] is True
    assert signal["legacy_star"] is True
    assert signal["reversal_star"] is True
    assert signal["symbol"] == "◎☆"

    readiness["checks"] = checks + [{"key": "equity", "status": "fail"}]
    signal = build_intuitive_signal(readiness, transition)'''
replace_once(test_buy, old_transition, new_transition)

write("tests/test_reversal_confirmed_star.py", '''import pandas as pd

from value_dislocation.decision import build_intuitive_signal
from value_dislocation.history import (
    build_star_events,
    reconcile_star_outcomes,
    star_validation_text_summary,
    upsert_daily_evaluations,
)


def _clear_readiness():
    checks = [
        {"key": key, "status": "pass"}
        for key in ("sales", "margin", "equity", "ocf", "forecast", "payout", "div_change", "trend")
    ]
    return {"decision_level": "consider", "evidence_score": 92, "checks": checks}


def _transition(*, score=5, return_20d=0.03, price=110.0, sma20=105.0, sma50=100.0, rising=True):
    return {
        "current_score": score,
        "escaped_downtrend": True,
        "current": {
            "latest_price": price,
            "sma20": sma20,
            "sma50": sma50,
            "sma20_rising": rising,
            "return_20d": return_20d,
        },
    }


def test_legacy_star_is_demoted_when_reversal_is_not_confirmed():
    signal = build_intuitive_signal(_clear_readiness(), _transition(score=3, return_20d=-0.02, rising=False))
    assert signal["legacy_star"] is True
    assert signal["reversal_star"] is False
    assert signal["star"] is False
    assert signal["symbol"] == "◎"
    assert "旧◎☆条件相当" in signal["detail"]


def test_reversal_star_requires_all_five_timing_gates():
    signal = build_intuitive_signal(_clear_readiness(), _transition())
    assert signal["symbol"] == "◎☆"
    assert all(signal["reversal_checks"].values())

    cases = [
        _transition(score=4),
        _transition(return_20d=-0.001),
        _transition(price=104.0),
        _transition(rising=False),
        _transition(sma20=99.0, sma50=100.0),
    ]
    for transition in cases:
        result = build_intuitive_signal(_clear_readiness(), transition)
        assert result["legacy_star"] is True
        assert result["reversal_star"] is False
        assert result["symbol"] == "◎"


def test_upsert_persists_old_and_new_star_eligibility(tmp_path):
    rows = pd.DataFrame([
        {
            "raw_code": "1111",
            "直感判定": "◎ 買い候補（反転確認待ち）",
            "判断メモ": "旧◎☆条件相当ですが、反転確認条件が未達です。",
            "selection_strategy": "value_dislocation",
            "最新株価": 100.0,
            "最新判定": "上昇転換の兆候",
            "evaluation_status": "当日評価済み",
        },
        {
            "raw_code": "2222",
            "直感判定": "◎☆ 反転確認済み候補",
            "判断メモ": "反転確認条件を満たしています。",
            "selection_strategy": "value_dislocation",
            "最新株価": 200.0,
            "最新判定": "上昇トレンド",
            "evaluation_status": "当日評価済み",
        },
    ])
    path = upsert_daily_evaluations(tmp_path, rows, evaluation_date="2026-09-20", analysis_as_of="2026-09-20")
    saved = pd.read_csv(path, dtype={"code": str}, compression="gzip")
    first = saved.loc[saved["code"] == "1111"].iloc[0]
    second = saved.loc[saved["code"] == "2222"].iloc[0]
    assert bool(first["legacy_star_eligible"]) is True
    assert bool(first["reversal_star_eligible"]) is False
    assert bool(second["legacy_star_eligible"]) is True
    assert bool(second["reversal_star_eligible"]) is True
    assert set(saved["star_rule_version"]) == {"reversal_v1"}


def test_rule_comparison_is_prospective_and_keeps_legacy_history():
    rows = pd.DataFrame([
        {"evaluation_date": "2026-09-20", "code": "1111", "selection_strategy": "value_dislocation", "intuitive_symbol": "◎", "legacy_star_eligible": True, "reversal_star_eligible": False, "star_rule_version": "reversal_v1", "latest_price": 100.0, "latest_market_date": "2026-09-20", "latest_trend": "上昇転換の兆候"},
        {"evaluation_date": "2026-09-20", "code": "2222", "selection_strategy": "value_dislocation", "intuitive_symbol": "◎☆", "legacy_star_eligible": True, "reversal_star_eligible": True, "star_rule_version": "reversal_v1", "latest_price": 100.0, "latest_market_date": "2026-09-20", "latest_trend": "上昇トレンド"},
        {"evaluation_date": "2026-10-12", "code": "1111", "selection_strategy": "value_dislocation", "intuitive_symbol": "◎", "legacy_star_eligible": True, "reversal_star_eligible": False, "star_rule_version": "reversal_v1", "latest_price": 95.0, "latest_market_date": "2026-10-12", "latest_trend": "方向感なし・もみ合い"},
        {"evaluation_date": "2026-10-12", "code": "2222", "selection_strategy": "value_dislocation", "intuitive_symbol": "◎☆", "legacy_star_eligible": True, "reversal_star_eligible": True, "star_rule_version": "reversal_v1", "latest_price": 108.0, "latest_market_date": "2026-10-12", "latest_trend": "上昇トレンド"},
    ])
    assert len(build_star_events(rows, star_mode="legacy")) == 2
    assert len(build_star_events(rows, star_mode="reversal")) == 1
    reconciled = reconcile_star_outcomes(rows)
    comparison = reconciled.attrs["star_rule_comparison"]
    legacy = comparison.loc[comparison["判定方式"] == "旧◎☆条件"].iloc[0]
    reversal = comparison.loc[comparison["判定方式"] == "反転確認◎☆"].iloc[0]
    assert int(legacy["開始イベント数"]) == 2
    assert int(reversal["開始イベント数"]) == 1
    assert float(legacy["20日プラス率"]) == 0.5
    assert float(reversal["20日プラス率"]) == 1.0

    summary_frame = pd.DataFrame({"期間": ["20日"], "平均リターン(%)": [8.0], "確定件数": [1]}).set_index("期間")
    lines = star_validation_text_summary(reconciled, summary_frame)
    assert any("新旧ルール比較" in line for line in lines)
    assert any("20日実績は旧条件" in line for line in lines)
''')

# 4) Version, blueprint, docs and task history.
for path in ["pyproject.toml", "src/value_dislocation/__init__.py", "tests/test_package_init.py", "tests/test_sort_performance_and_readme_structure.py"]:
    text = read(path)
    if "0.6.60" not in text:
        raise RuntimeError(f"{path}: expected 0.6.60")
    write(path, text.replace("0.6.60", "0.6.61"))

blueprint = read("harness/app_blueprint.yaml")
blueprint = blueprint.replace("blueprint_version: 0.6.60", "blueprint_version: 0.6.61", 1)
blueprint = blueprint.replace("- strict_quality_star_badge\n", "- strict_quality_star_badge\n- reversal_confirmed_quality_star\n- legacy_vs_reversal_star_outcome_comparison\n", 1)
blueprint = blueprint.replace("- quality_star_must_not_override_negative_core_checks\n", "- quality_star_must_not_override_negative_core_checks\n- quality_star_must_require_confirmed_short_term_reversal\n- legacy_star_eligibility_must_remain_comparable_after_rule_change\n", 1)
write("harness/app_blueprint.yaml", blueprint)

readme = read("README.md")
readme = readme.replace("Version: **0.6.60**", "Version: **0.6.61**", 1)
marker = "### v0.6.60 旧実績データの期間列後方互換修正"
section = '''### v0.6.61 ◎☆を反転確認済みの最上位評価へ厳格化

- 従来の◎☆品質条件に加え、`trend_score >= 5`、20日騰落率0%以上、株価>MA20、MA20上向き、MA20>MA50をすべて満たす場合だけ◎☆とします。
- 従来なら◎☆だったものの反転確認条件が足りない銘柄は◎「買い候補（反転確認待ち）」として残し、候補自体を捨てません。
- v0.6.61以降は旧◎☆条件と反転確認◎☆の適格フラグを評価履歴へ同時保存し、実績検証の分析結果サマリで開始イベント数と20日実績を比較します。
- 比較は将来情報を使わず、v0.6.61以降に保存された同一評価期間を使う前向き比較です。旧履歴を新ルールだったと推測して書き換えません。

'''
if marker not in readme:
    raise RuntimeError("README version marker not found")
readme = readme.replace(marker, section + marker, 1)
write("README.md", readme)

changelog = read("CHANGELOG.md")
write("CHANGELOG.md", '''## v0.6.61
- ◎☆を「品質条件を満たす」だけでなく短期反転を確認した最上位評価へ厳格化。
- 追加必須条件: trend_score>=5、20日騰落率>=0、株価>MA20、MA20上向き、MA20>MA50。
- 旧◎☆相当だが反転未確認の銘柄は◎へ降格し、「反転確認待ち」と明示。
- v0.6.61以降の評価履歴に旧ルール/新ルール双方の適格フラグを保存し、実績サマリで新旧のイベント数と20日成績を前向き比較。
- 過去の◎☆履歴は推測で再分類せず、そのまま保持。

''' + changelog)

tasks = read("tasks/CURRENT.md")
write("tasks/CURRENT.md", '''## v0.6.61 reversal-confirmed star

- [x] ◎☆を短期反転確認済みの最上位評価へ厳格化する。
- [x] trend_score>=5 / 20日騰落率>=0 / 株価>MA20 / MA20上向き / MA20>MA50 をすべて必須にする。
- [x] 旧◎☆相当だが反転未確認の銘柄は◎として残す。
- [x] 旧ルールと新ルールの適格フラグを同時保存し、実績サマリで前向き比較する。
- [x] 過去の評価を将来情報で再分類しない。

''' + tasks)

write("docs/20_REVERSAL_CONFIRMED_STAR.md", '''# v0.6.61 反転確認済み◎☆

## 目的
従来の◎☆は財務・業績・トレンドの主要チェックに欠点がないことを重視していましたが、20日前後の短期では下落継続中の銘柄も含み得ました。v0.6.61では、◎☆を「品質が良い」だけでなく「値動きが実際に反転し始めた」候補へ限定します。

## 新しい◎☆必須条件
従来の◎☆条件を満たした上で、以下をすべて満たす必要があります。

1. トレンドスコア >= 5
2. 直近20日騰落率 >= 0%
3. 最新株価 > MA20
4. MA20が上向き
5. MA20 > MA50

どれか1つでも未達なら◎☆にはせず、従来◎☆相当であれば◎「買い候補（反転確認待ち）」として継続監視します。

## 旧ルールとの比較
v0.6.61以降の保存評価には `legacy_star_eligible`、`reversal_star_eligible`、`star_rule_version` を保存します。履歴・実績検証の分析結果サマリでは、同じ評価期間について旧◎☆条件と反転確認◎☆の開始イベント数、および確定後の20日平均/プラス率を比較します。

比較は前向き（prospective）です。v0.6.60以前の履歴には当時の反転ゲート値が保存されていないため、将来情報を使って新ルールだったと推測することはしません。
''')

print("v0.6.61 patch applied")
