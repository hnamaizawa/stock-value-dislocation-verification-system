from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

REVIEW_SCHEMA_VERSION = "1.0"
APPROVAL_STATUSES = {"approved", "pending", "rejected"}


def normalize_security_code(value: str) -> str:
    digits = re.sub(r"\D", "", str(value))
    if len(digits) >= 4:
        return digits[:4]
    return digits or "unknown"


def default_external_event_review(code: str, name: str = "") -> dict[str, Any]:
    """Return an unsaved review prefilled with editable guidance samples.

    These values are intentionally generic and the approval status remains pending.
    They are shown only when no saved review exists, so users can edit a concrete
    example instead of starting from an empty form. Structured invalidation samples
    are disabled by default to avoid generating warnings before the user adopts them.
    """
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "code": normalize_security_code(code),
        "name": str(name),
        "evaluation_date": datetime.now().astimezone().date().isoformat(),
        "reviewer": "確認者名を入力",
        "decline_factor": "[サンプル] 市場全体のリスク回避や一時的な需給悪化が主因かを確認。会社固有の構造悪化が主因ではないか一次資料で切り分ける。",
        "primary_source": {
            "document_id": "[サンプル] 最新の決算短信・適時開示・有価証券報告書",
            "published_at": "[サンプル] YYYY-MM-DD HH:MM",
            "location": "[サンプル] 業績予想・事業概況・リスク説明の該当ページ",
            "summary": "[サンプル] 会社予想の変更有無、利益率・キャッシュフローの悪化が一時要因か構造要因かを要約する。",
        },
        "assessment": {
            "external_factor_degree": 0.6,
            "temporariness_probability": 0.6,
            "catalyst_probability": 0.5,
            "structural_risk": 0.3,
        },
        "recovery_catalyst_and_deadline": "[サンプル] 次回決算までに売上・利益率・会社予想の改善または維持を確認。期限は次回決算発表日を目安に更新する。",
        "invalidation_conditions": "[サンプル] 会社予想の大幅下方修正、営業CFの継続悪化、減配など、当初仮説を維持できない事実が出たら再評価する。",
        "structured_invalidation_conditions": [
            {
                "metric": "operating_margin",
                "operator": "<",
                "threshold": 8.0,
                "unit": "%",
                "enabled": False,
                "note": "[サンプル] 自社に適した基準へ変更してから有効化",
            }
        ],
        "approval_status": "pending",
        "updated_at": "",
    }


def _validate_probability(value: Any, field: str) -> float:
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{field} must be between 0 and 1")
    return number


def validate_external_event_review(document: dict[str, Any]) -> dict[str, Any]:
    if document.get("schema_version") != REVIEW_SCHEMA_VERSION:
        raise ValueError("Unsupported external-event review schema version")
    status = str(document.get("approval_status", "pending"))
    if status not in APPROVAL_STATUSES:
        raise ValueError("Invalid approval_status")
    source = document.get("primary_source")
    assessment = document.get("assessment")
    if not isinstance(source, dict) or not isinstance(assessment, dict):
        raise ValueError("Invalid external-event review structure")
    structured = document.get("structured_invalidation_conditions", [])
    if structured is not None and not isinstance(structured, list):
        raise ValueError("structured_invalidation_conditions must be a list")
    for field in (
        "external_factor_degree",
        "temporariness_probability",
        "catalyst_probability",
        "structural_risk",
    ):
        _validate_probability(assessment.get(field, 0.5), field)
    return document


def review_path(directory: Path, code: str) -> Path:
    return directory / f"{normalize_security_code(code)}.json"


def load_external_event_review(directory: Path, code: str, name: str = "") -> dict[str, Any]:
    path = review_path(directory, code)
    if not path.exists():
        return default_external_event_review(code, name)
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_external_event_review(data)
    # Keep current master name if an older saved review had no name.
    if name and not data.get("name"):
        data["name"] = str(name)
    return data


def save_external_event_review(directory: Path, document: dict[str, Any]) -> Path:
    data = dict(document)
    data["schema_version"] = REVIEW_SCHEMA_VERSION
    data["code"] = normalize_security_code(str(data.get("code", "")))
    data["updated_at"] = datetime.now().astimezone().isoformat()
    validate_external_event_review(data)
    directory.mkdir(parents=True, exist_ok=True)
    path = review_path(directory, data["code"])
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def approval_completeness_issues(document: dict[str, Any] | None) -> list[str]:
    """Return optional review fields that are still blank.

    These are guidance only. They are deliberately not an approval gate: the
    non-negotiable invariant requires a human-approved external-event review,
    not mandatory completion of every template field.
    """
    if not isinstance(document, dict):
        return ["レビューがありません"]
    source = document.get("primary_source") if isinstance(document.get("primary_source"), dict) else {}
    optional = {
        "レビュアー": document.get("reviewer"),
        "下落要因": document.get("decline_factor"),
        "一次資料の文書ID": source.get("document_id"),
        "一次資料の要約": source.get("summary"),
        "回復カタリストと期限": document.get("recovery_catalyst_and_deadline"),
        "仮説無効化条件": document.get("invalidation_conditions"),
    }
    return [name for name, value in optional.items() if not str(value or "").strip()]


def external_event_review_is_approved(document: dict[str, Any] | None) -> bool:
    if not isinstance(document, dict):
        return False
    try:
        validate_external_event_review(document)
    except (TypeError, ValueError):
        return False
    return document.get("approval_status") == "approved"


def candidate_order_preview_allowed(
    document: dict[str, Any] | None,
    *,
    data_fresh: bool,
    manual_checks_complete: bool,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not external_event_review_is_approved(document):
        reasons.append("外的要因レビューが approved ではありません")
    if not data_fresh:
        reasons.append("市場データの鮮度条件を満たしていません")
    if not manual_checks_complete:
        reasons.append("注文前の人手確認が完了していません")
    return not reasons, reasons
