import json
from pathlib import Path

import pandas as pd

from value_dislocation.hypothesis_invalidation import (
    evaluate_hypothesis_invalidation,
    structured_conditions_from_ui_rows,
    evaluate_saved_reviews,
)


def _review(structured, free_text=""):
    return {
        "code": "7203",
        "name": "テスト自動車",
        "invalidation_conditions": free_text,
        "structured_invalidation_conditions": structured,
    }


def test_structured_condition_is_breached():
    review = _review([
        {"metric": "operating_margin", "operator": "<", "threshold": 8.0, "enabled": True}
    ])
    result = evaluate_hypothesis_invalidation(review, {"operating_margin": 0.071})
    assert result["status"] == "breached"
    assert len(result["breached"]) == 1
    assert result["breached"][0]["actual_display"] == "7.10%"


def test_structured_condition_is_not_breached():
    review = _review([
        {"metric": "operating_margin", "operator": "<", "threshold": 8.0, "enabled": True}
    ])
    result = evaluate_hypothesis_invalidation(review, {"operating_margin": 0.102})
    assert result["status"] == "clear"
    assert result["breached"] == []


def test_free_text_is_manual_review_only():
    result = evaluate_hypothesis_invalidation(
        _review([], "次回決算の説明内容が悪化したら再確認"),
        {"operating_margin": 0.10},
    )
    assert result["status"] == "manual_review"
    assert result["manual_review_required"] is True


def test_missing_metric_is_unevaluable():
    review = _review([
        {"metric": "forecast_operating_profit", "operator": "<", "threshold": 100_000, "enabled": True}
    ])
    result = evaluate_hypothesis_invalidation(review, {})
    assert result["status"] == "unevaluable"
    assert len(result["unevaluable"]) == 1


def test_saved_reviews_are_recalculated_from_current_features_each_time(tmp_path: Path):
    review_dir = tmp_path / "reviews"
    review_dir.mkdir()
    (review_dir / "7203.json").write_text(
        json.dumps(_review([
            {"metric": "operating_margin", "operator": "<", "threshold": 8.0, "enabled": True}
        ]), ensure_ascii=False),
        encoding="utf-8",
    )
    first = evaluate_saved_reviews(review_dir, pd.DataFrame([{"code": "7203", "operating_margin": 0.10}]))
    second = evaluate_saved_reviews(review_dir, pd.DataFrame([{"code": "7203", "operating_margin": 0.06}]))
    assert first.iloc[0]["status"] == "clear"
    assert second.iloc[0]["status"] == "breached"


def test_evaluator_has_no_jquants_fetch_dependency():
    source = Path("src/value_dislocation/hypothesis_invalidation.py").read_text(encoding="utf-8")
    assert "fetch_and_curate_jquants" not in source
    assert "data.jquants" not in source
    assert "JQuants" not in source


def test_structured_conditions_from_ui_rows_saves_all_rows_in_one_pass():
    rows = [
        {"有効": True, "指標": "営業利益率", "比較": "<", "閾値": 8.0, "メモ": "first"},
        {"有効": True, "指標": "自己資本比率", "比較": "<", "閾値": 40.0, "メモ": "second"},
    ]
    result = structured_conditions_from_ui_rows(rows)
    assert len(result) == 2
    assert result[0]["metric"] == "operating_margin"
    assert result[0]["threshold"] == 8.0
    assert result[0]["note"] == "first"
    assert result[1]["metric"] == "equity_ratio"
    assert result[1]["threshold"] == 40.0
    assert result[1]["note"] == "second"


def test_threshold_input_format_is_natural_without_forced_trailing_zeroes():
    from value_dislocation.hypothesis_invalidation import format_threshold_input_value

    assert format_threshold_input_value(50.0) == "50"
    assert format_threshold_input_value(7.5) == "7.5"
    assert format_threshold_input_value(8.25) == "8.25"
    assert format_threshold_input_value(0.0) == "0"


def test_structured_conditions_accept_threshold_text_values():
    from value_dislocation.hypothesis_invalidation import structured_conditions_from_ui_rows

    rows = [{
        "有効": True,
        "指標": "営業利益率",
        "比較": "<",
        "閾値": "7.5",
        "メモ": "次回決算",
    }]
    result = structured_conditions_from_ui_rows(rows)
    assert len(result) == 1
    assert result[0]["threshold"] == 7.5
