from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import math


@dataclass(frozen=True)
class Check:
    key: str
    label: str
    status: str  # pass, warn, fail, unknown
    detail: str
    weight: int


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _check(key: str, label: str, value: float | None, pass_rule, warn_rule, detail: str, weight: int) -> Check:
    if value is None:
        return Check(key, label, "unknown", f"{detail}（データなし）", weight)
    if pass_rule(value):
        status = "pass"
    elif warn_rule(value):
        status = "warn"
    else:
        status = "fail"
    return Check(key, label, status, detail, weight)


def build_buy_readiness(
    metrics: dict[str, Any],
    *,
    analyst: dict[str, Any] | None = None,
    external_quote_available: bool = False,
    benchmark_available: bool | None = None,
    trend: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an explainable, non-advisory purchase-decision summary.

    This does not produce a buy recommendation.  It organizes favorable evidence,
    warnings, blockers and missing information so a human can decide what to verify.
    """
    analyst = analyst or {}
    trend = trend or {}
    drawdown = _number(metrics.get("drawdown_52w"))
    relative = _number(metrics.get("relative_return_6m"))
    sales = _number(metrics.get("sales_cagr_3y"))
    margin = _number(metrics.get("operating_margin"))
    equity = _number(metrics.get("equity_ratio"))
    ocf = _number(metrics.get("operating_cf_positive_ratio_3y"))
    cash_quality = _number(metrics.get("cash_conversion_ratio"))
    margin_change = _number(metrics.get("operating_margin_change_3y"))
    forecast_revision = _number(metrics.get("forecast_revision_rate"))
    sector_relative = _number(metrics.get("sector_relative_return_6m"))
    forecast = _number(metrics.get("forecast_op_growth"))
    div_yield = _number(metrics.get("forecast_dividend_yield"))
    payout = _number(metrics.get("payout_ratio"))
    div_change = _number(metrics.get("forecast_dividend_change_rate"))
    target_upside = _number(analyst.get("upside_to_mean_target"))
    trend_score = _number(trend.get("trend_score"))
    rsi14 = _number(trend.get("rsi14"))
    return_20d = _number(trend.get("return_20d"))
    volume_ratio = _number(trend.get("volume_ratio_20d"))

    checks = [
        _check("drawdown", "十分な株価下落", drawdown, lambda x: x <= -0.20, lambda x: x <= -0.12,
               f"52週高値比 {drawdown:.1%}" if drawdown is not None else "52週高値比", 12),
        _check("relative", "市場以上の下落", relative, lambda x: x <= -0.08, lambda x: x <= 0,
               f"市場比較相対 {relative:.1%}" if relative is not None else "市場比較相対", 8),
        _check("sales", "売上トレンド", sales, lambda x: x >= 0, lambda x: x >= -0.05,
               f"売上CAGR {sales:.1%}" if sales is not None else "売上CAGR", 10),
        _check("margin", "本業の収益性", margin, lambda x: x >= 0.05, lambda x: x > 0,
               f"営業利益率 {margin:.1%}" if margin is not None else "営業利益率", 10),
        _check("equity", "財務余力", equity, lambda x: x >= 0.40, lambda x: x >= 0.25,
               f"自己資本比率 {equity:.1%}" if equity is not None else "自己資本比率", 12),
        _check("ocf", "現金創出の継続性", ocf, lambda x: x >= 0.999, lambda x: x >= 0.66,
               f"営業CFプラス比率 {ocf:.0%}" if ocf is not None else "営業CF履歴", 12),
        _check("cash_quality", "利益の質", cash_quality, lambda x: x >= 0.80, lambda x: x >= 0.50,
               f"営業CF÷営業利益 {cash_quality:.0%}" if cash_quality is not None else "利益現金化率", 8),
        _check("margin_stability", "採算の安定性", margin_change, lambda x: x >= -0.02, lambda x: x >= -0.05,
               f"営業利益率変化 {margin_change:+.1%}" if margin_change is not None else "営業利益率変化", 6),
        _check("forecast_revision", "会社予想の修正方向", forecast_revision, lambda x: x >= -0.05, lambda x: x >= -0.15,
               f"同一年度の前回予想比 {forecast_revision:+.1%}" if forecast_revision is not None else "会社予想修正", 8),
        _check("sector_relative", "同業他社対比", sector_relative, lambda x: x >= -0.10, lambda x: x >= -0.20,
               f"業種中央値比 {sector_relative:+.1%}" if sector_relative is not None else "業種中央値比", 6),
        _check("forecast", "会社予想", forecast, lambda x: x >= 0, lambda x: x >= -0.15,
               f"予想営業利益変化 {forecast:.1%}" if forecast is not None else "会社予想", 10),
        _check("dividend", "配当の魅力", div_yield, lambda x: 0.025 <= x <= 0.06, lambda x: 0 < x <= 0.08,
               f"予想配当利回り {div_yield:.1%}" if div_yield is not None else "予想配当利回り", 8),
        _check("payout", "配当の持続性", payout, lambda x: x <= 0.60, lambda x: x <= 0.85,
               f"予想配当性向 {payout:.1%}" if payout is not None else "配当性向", 8),
        _check("div_change", "減配リスク", div_change, lambda x: x >= 0, lambda x: x >= -0.10,
               f"予想配当変化 {div_change:.1%}" if div_change is not None else "配当変化", 5),
        _check("analyst", "外部評価の補助", target_upside, lambda x: x >= 0.10, lambda x: x >= -0.05,
               f"平均目標株価への乖離 {target_upside:.1%}" if target_upside is not None else "目標株価情報", 5),
        _check("trend", "価格トレンド", trend_score, lambda x: x >= 2, lambda x: x >= -1,
               f"{trend.get('trend_state', 'トレンド不明')}（スコア {trend_score:.0f}）" if trend_score is not None else "トレンド情報", 12),
        _check("momentum", "直近20日モメンタム", return_20d, lambda x: 0 <= x <= 0.15, lambda x: -0.10 <= x <= 0.25,
               f"20日騰落率 {return_20d:.1%}" if return_20d is not None else "20日騰落率", 6),
        _check("rsi", "短期の過熱感", rsi14, lambda x: 40 <= x <= 65, lambda x: 30 <= x < 75,
               f"RSI(14) {rsi14:.1f}" if rsi14 is not None else "RSI(14)", 5),
        _check("volume", "出来高の確認", volume_ratio, lambda x: 1.2 <= x <= 3.0, lambda x: 0.7 <= x < 4.0,
               f"20日平均比 {volume_ratio:.2f}倍" if volume_ratio is not None else "出来高20日平均比", 4),
    ]

    if benchmark_available is False:
        checks = [Check(c.key, c.label, "unknown", "市場比較データなし", c.weight) if c.key == "relative" else c for c in checks]

    weighted_total = sum(c.weight for c in checks if c.status != "unknown")
    weighted_score = sum(c.weight * ({"pass": 1.0, "warn": 0.5, "fail": 0.0}[c.status]) for c in checks if c.status != "unknown")
    evidence_score = round(100 * weighted_score / weighted_total) if weighted_total else 0
    failures = [c for c in checks if c.status == "fail"]
    warnings = [c for c in checks if c.status in {"warn", "unknown"}]
    positives = [c for c in checks if c.status == "pass"]

    hard_failure_keys = {
        "equity", "ocf", "cash_quality", "margin_stability",
        "forecast_revision", "sector_relative", "forecast", "margin", "trend",
    }
    hard_failures = [c for c in failures if c.key in hard_failure_keys]
    if hard_failures:
        decision = "見送り優先"
        decision_level = "stop"
        reason = "財務・キャッシュフロー・会社予想などに重要な弱点があります。"
    elif evidence_score >= 75 and external_quote_available:
        decision = "追加確認後に条件付きで検討"
        decision_level = "consider"
        reason = "定量面の根拠は比較的揃っていますが、外的要因と最新開示の人手確認が必要です。"
    elif evidence_score >= 55:
        decision = "調査継続"
        decision_level = "research"
        reason = "有利な材料と注意材料が混在しています。未確認事項を解消してから判断してください。"
    else:
        decision = "現時点では見送り"
        decision_level = "stop"
        reason = "買付判断を支える定量根拠が十分ではありません。"

    return {
        "decision": decision,
        "decision_level": decision_level,
        "reason": reason,
        "evidence_score": evidence_score,
        "checks": [c.__dict__ for c in checks],
        "positives": [c.__dict__ for c in positives],
        "warnings": [c.__dict__ for c in warnings],
        "failures": [c.__dict__ for c in failures],
        "external_quote_available": external_quote_available,
    }



REVERSAL_STAR_RULE_VERSION = "reversal_v1"


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
    structural_keys = {"cash_quality", "margin_stability", "forecast_revision", "sector_relative"}
    structural_checks = [item for item in checks if item.get("key") in structural_keys]
    # Missing optional structural evidence does not fabricate a failure, but a known
    # warn/fail blocks the highest ◎☆ quality badge until the concern is resolved.
    structural_clear = all(item.get("status") in {"pass", "unknown"} for item in structural_checks)
    core_clear = (
        bool(core_checks)
        and all(item.get("status") == "pass" for item in core_checks)
        and structural_clear
    )
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


def build_entry_price_guidance(
    current_price: float,
    trend: dict[str, Any] | None = None,
    trend_transition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an explainable entry-price reference range, not an order recommendation."""
    trend = trend or {}
    trend_transition = trend_transition or {}
    price = _number(current_price)
    if price is None or price <= 0:
        return {"status": "算出不能", "zone_low": None, "zone_high": None, "rationale": "有効な最新株価がありません。"}

    sma20 = _number(trend.get("sma20"))
    sma50 = _number(trend.get("sma50"))
    low20 = _number(trend.get("low20"))
    low60 = _number(trend.get("low60"))
    rsi = _number(trend.get("rsi14"))
    score = int(_number(trend.get("trend_score")) or 0)
    escaped = bool(trend_transition.get("escaped_downtrend"))

    supports = [v for v in (sma20, sma50, low20, low60) if v is not None and v > 0 and v <= price * 1.10]
    primary = sma20 if sma20 is not None else (sma50 if sma50 is not None else price * 0.95)
    secondary = sma50 if sma50 is not None else (low20 if low20 is not None else price * 0.90)

    if score <= -2:
        anchor = low20 or low60 or secondary
        zone_low, zone_high = anchor * 0.98, anchor * 1.02
        status = "待機優先"
        rationale = "下降トレンド中です。安値付近だけで買わず、20日線回復や安値切り上げを確認してから再評価します。"
    elif rsi is not None and rsi >= 72:
        anchor = sma20 or price * 0.95
        zone_low, zone_high = anchor * 0.98, anchor * 1.01
        status = "押し目待ち"
        rationale = "短期的な過熱感があります。現在値を追わず、20日線付近への押し目を参考にします。"
    elif score >= 2 or escaped:
        zone_low, zone_high = primary * 0.98, primary * 1.02
        status = "分割買い検討帯"
        rationale = "最新トレンドが改善しています。20日線付近を第1候補とし、一括ではなく分割で検討します。"
    else:
        upper_anchor = min(v for v in (primary, price * 0.97) if v is not None)
        lower_anchor = secondary if secondary is not None else price * 0.90
        zone_low, zone_high = min(lower_anchor, upper_anchor) * 0.98, max(lower_anchor, upper_anchor) * 1.01
        status = "反転確認待ち"
        rationale = "方向感が弱いため、提示帯への下落だけでなく、20日線回復や出来高増加を確認します。"

    zone_low = max(0.1, min(zone_low, zone_high))
    zone_high = max(zone_low, zone_high)
    chase_limit = price * 1.03 if score >= 2 and (rsi is None or rsi < 70) else price
    reconsider_candidates = [v for v in (low20, low60, sma50) if v is not None and v > 0]
    reconsider_below = min(reconsider_candidates) * 0.97 if reconsider_candidates else price * 0.85
    return {
        "status": status,
        "zone_low": round(zone_low, 1),
        "zone_high": round(zone_high, 1),
        "current_price": round(price, 1),
        "chase_limit": round(chase_limit, 1),
        "reconsider_below": round(reconsider_below, 1),
        "rationale": rationale,
        "support_levels": [round(v, 1) for v in sorted(set(supports), reverse=True)[:4]],
    }


def build_split_entry_plan(
    current_price: float,
    budget_yen: float,
    *,
    board_lot: int = 100,
    discounts: tuple[float, ...] = (0.0, 0.07, 0.15),
    weights: tuple[float, ...] = (0.40, 0.30, 0.30),
) -> list[dict[str, Any]]:
    if current_price <= 0 or budget_yen <= 0 or board_lot <= 0:
        return []
    rows: list[dict[str, Any]] = []
    for index, (discount, weight) in enumerate(zip(discounts, weights), start=1):
        limit_price = current_price * (1 - discount)
        allocated = budget_yen * weight
        shares = int(allocated // (limit_price * board_lot)) * board_lot
        rows.append({
            "回": index,
            "指値目安": round(limit_price, 1),
            "現在値から": f"-{discount:.0%}" if discount else "現在値付近",
            "株数": shares,
            "概算金額": round(shares * limit_price),
            "資金配分": f"{weight:.0%}",
        })
    return rows
