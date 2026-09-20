import pandas as pd

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
