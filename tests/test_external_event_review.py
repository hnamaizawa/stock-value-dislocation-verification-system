import json
from pathlib import Path

import pytest

from value_dislocation.external_event_review import (
    candidate_order_preview_allowed,
    external_event_review_is_approved,
    load_external_event_review,
    save_external_event_review,
)


def _doc(status: str = "pending") -> dict:
    return {
        "schema_version": "1.0",
        "code": "7203",
        "name": "テスト自動車",
        "evaluation_date": "2026-08-11",
        "reviewer": "tester",
        "decline_factor": "外部要因のテスト",
        "primary_source": {
            "document_id": "TDNET-001",
            "published_at": "2026-08-10 15:00",
            "location": "1ページ",
            "summary": "一次資料の要約",
        },
        "assessment": {
            "external_factor_degree": 0.8,
            "temporariness_probability": 0.7,
            "catalyst_probability": 0.6,
            "structural_risk": 0.2,
        },
        "recovery_catalyst_and_deadline": "3か月以内の需要回復を確認",
        "invalidation_conditions": "会社予想の大幅下方修正",
        "approval_status": status,
    }


def test_external_event_review_round_trip(tmp_path: Path):
    path = save_external_event_review(tmp_path, _doc("approved"))
    assert path.name == "7203.json"
    loaded = load_external_event_review(tmp_path, "72030", "テスト自動車")
    assert loaded["approval_status"] == "approved"
    assert loaded["primary_source"]["document_id"] == "TDNET-001"
    assert loaded["assessment"]["structural_risk"] == 0.2
    assert loaded["updated_at"]


@pytest.mark.parametrize("status", ["pending", "rejected"])
def test_unapproved_review_blocks_order_preview(tmp_path: Path, status: str):
    saved = save_external_event_review(tmp_path, _doc(status))
    review = json.loads(saved.read_text(encoding="utf-8"))
    allowed, reasons = candidate_order_preview_allowed(
        review, data_fresh=True, manual_checks_complete=True
    )
    assert allowed is False
    assert any("approved" in reason for reason in reasons)


def test_approved_review_still_requires_other_gates():
    review = _doc("approved")
    assert external_event_review_is_approved(review)
    allowed, reasons = candidate_order_preview_allowed(
        review, data_fresh=False, manual_checks_complete=True
    )
    assert not allowed
    assert any("鮮度" in reason for reason in reasons)
    allowed, reasons = candidate_order_preview_allowed(
        review, data_fresh=True, manual_checks_complete=False
    )
    assert not allowed
    assert any("人手確認" in reason for reason in reasons)


def test_approved_review_allows_preview_only_when_all_gates_pass():
    allowed, reasons = candidate_order_preview_allowed(
        _doc("approved"), data_fresh=True, manual_checks_complete=True
    )
    assert allowed is True
    assert reasons == []


def test_corrupt_saved_review_is_not_approved(tmp_path: Path):
    (tmp_path / "7203.json").write_text('{"approval_status":"approved"}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_external_event_review(tmp_path, "7203")


def test_approved_status_allows_optional_fields_to_be_blank():
    review = _doc("approved")
    review["reviewer"] = ""
    review["decline_factor"] = ""
    review["primary_source"]["document_id"] = ""
    review["primary_source"]["summary"] = ""
    review["recovery_catalyst_and_deadline"] = ""
    review["invalidation_conditions"] = ""
    assert external_event_review_is_approved(review) is True
    allowed, reasons = candidate_order_preview_allowed(
        review, data_fresh=True, manual_checks_complete=True
    )
    assert allowed is True
    assert reasons == []


def test_structured_invalidation_conditions_round_trip(tmp_path: Path):
    review = _doc("approved")
    review["structured_invalidation_conditions"] = [
        {"metric": "operating_margin", "operator": "<", "threshold": 8.0, "unit": "%", "enabled": True, "note": "次回決算"}
    ]
    save_external_event_review(tmp_path, review)
    loaded = load_external_event_review(tmp_path, "7203")
    assert loaded["structured_invalidation_conditions"][0]["metric"] == "operating_margin"


def test_default_review_prefills_editable_guidance_samples(tmp_path: Path):
    review = load_external_event_review(tmp_path, "7203", "テスト自動車")
    assert review["approval_status"] == "pending"
    assert review["evaluation_date"]
    assert "サンプル" in review["decline_factor"]
    assert "サンプル" in review["primary_source"]["document_id"]
    assert "サンプル" in review["recovery_catalyst_and_deadline"]
    assert "サンプル" in review["invalidation_conditions"]
    assert review["structured_invalidation_conditions"]
    assert review["structured_invalidation_conditions"][0]["enabled"] is False
