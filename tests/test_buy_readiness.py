from value_dislocation.decision import build_buy_readiness, build_split_entry_plan


def test_buy_readiness_organizes_positive_and_negative_evidence():
    result = build_buy_readiness(
        {
            "drawdown_52w": -0.30,
            "relative_return_6m": -0.12,
            "sales_cagr_3y": 0.04,
            "operating_margin": 0.12,
            "equity_ratio": 0.55,
            "operating_cf_positive_ratio_3y": 1.0,
            "forecast_op_growth": 0.05,
            "forecast_dividend_yield": 0.035,
            "payout_ratio": 0.45,
            "forecast_dividend_change_rate": 0.05,
        },
        analyst={"upside_to_mean_target": 0.20},
        external_quote_available=True,
        benchmark_available=True,
    )
    assert result["evidence_score"] >= 75
    assert result["decision_level"] == "consider"
    assert len(result["positives"]) >= 8


def test_buy_readiness_stops_on_hard_financial_failure():
    result = build_buy_readiness(
        {
            "drawdown_52w": -0.40,
            "sales_cagr_3y": -0.15,
            "operating_margin": -0.05,
            "equity_ratio": 0.15,
            "operating_cf_positive_ratio_3y": 0.0,
            "forecast_op_growth": -0.40,
        },
        external_quote_available=True,
        benchmark_available=False,
    )
    assert result["decision_level"] == "stop"
    assert result["failures"]


def test_split_entry_plan_respects_board_lot_and_budget():
    rows = build_split_entry_plan(1000, 300000, board_lot=100)
    assert len(rows) == 3
    assert all(row["株数"] % 100 == 0 for row in rows)
    assert sum(row["概算金額"] for row in rows) <= 300000


def test_buy_readiness_includes_trend_and_stops_on_strong_downtrend():
    result = build_buy_readiness(
        {
            "drawdown_52w": -0.30,
            "sales_cagr_3y": 0.03,
            "operating_margin": 0.08,
            "equity_ratio": 0.50,
            "operating_cf_positive_ratio_3y": 1.0,
            "forecast_op_growth": 0.02,
        },
        trend={
            "trend_state": "明確な下向きトレンド",
            "trend_score": -6,
            "return_20d": -0.14,
            "rsi14": 27,
            "volume_ratio_20d": 1.8,
        },
        external_quote_available=True,
    )
    assert result["decision_level"] == "stop"
    assert any(item["key"] == "trend" for item in result["failures"])


def test_intuitive_signal_and_entry_price_guidance():
    from value_dislocation.decision import build_intuitive_signal, build_entry_price_guidance

    readiness = {
        "decision_level": "consider",
        "evidence_score": 82,
    }
    transition = {"escaped_downtrend": True, "current_score": 3}
    signal = build_intuitive_signal(readiness, transition)
    assert signal["symbol"] == "◎"
    assert signal["label"] == "買い候補"

    guidance = build_entry_price_guidance(
        1000,
        {
            "trend_score": 3,
            "sma20": 960,
            "sma50": 910,
            "low20": 920,
            "low60": 860,
            "rsi14": 58,
        },
        transition,
    )
    assert guidance["status"] == "分割買い検討帯"
    assert guidance["zone_low"] < guidance["zone_high"]
    assert guidance["reconsider_below"] < 1000


def test_entry_price_guidance_waits_during_downtrend():
    from value_dislocation.decision import build_entry_price_guidance

    guidance = build_entry_price_guidance(
        1000,
        {"trend_score": -4, "sma20": 1050, "sma50": 1100, "low20": 950, "low60": 900, "rsi14": 28},
        {"escaped_downtrend": False},
    )
    assert guidance["status"] == "待機優先"
    assert guidance["zone_high"] <= 1000


def test_intuitive_signal_adds_star_only_when_core_checks_are_clear():
    from value_dislocation.decision import build_intuitive_signal

    checks = [
        {"key": key, "status": "pass"}
        for key in ("sales", "margin", "equity", "ocf", "forecast", "payout", "div_change", "trend")
    ]
    readiness = {"decision_level": "consider", "evidence_score": 92, "checks": checks}
    signal = build_intuitive_signal(readiness, {"current_score": 5, "escaped_downtrend": True})
    assert signal["star"] is True
    assert signal["symbol"] == "◎☆"

    readiness["checks"] = checks + [{"key": "equity", "status": "fail"}]
    signal = build_intuitive_signal(readiness, {"current_score": 5, "escaped_downtrend": True})
    assert signal["star"] is False
    assert signal["symbol"] == "◎"
