from __future__ import annotations

import re
from typing import Any, Dict, List

from .normalizer import ISO_RE

NUMERIC_RE = re.compile(r"^\d+$")
PHONE_RE = re.compile(r"^\d{2,4}-?\d{2,4}-?\d{3,4}$")
POSTAL_RE = re.compile(r"^\d{3}-?\d{4}$")

UNKNOWN_MARKERS = {"不明", "要確認", "対象外", "unknown", "todo"}


def _required_flag(required: Any) -> bool:
    text = str(required).strip().lower()
    return text in {"true", "1", "yes", "必須", "required"} or "必須" in str(required)


def validate_answers(
    fields: List[Dict[str, Any]],
    normalized_answers: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []

    for field in fields:
        field_id = str(field.get("field_id", "")).strip()
        if not field_id:
            continue

        answer_obj = normalized_answers.get(field_id, {"raw": "", "norm": ""})
        raw = answer_obj.get("raw", "").strip()
        norm = answer_obj.get("norm", "").strip()
        fmt = str(field.get("format", ""))

        if _required_flag(field.get("required")):
            if raw == "":
                issues.append(
                    {
                        "field_id": field_id,
                        "severity": "error",
                        "message": "必須項目が未入力です。",
                    }
                )
            elif raw.lower() in UNKNOWN_MARKERS or raw in UNKNOWN_MARKERS:
                issues.append(
                    {
                        "field_id": field_id,
                        "severity": "warning",
                        "message": "必須項目ですが『要確認/不明』として保存されています。",
                    }
                )

        if norm == "":
            continue

        if ("数字" in fmt or "number" in fmt.lower()) and not NUMERIC_RE.fullmatch(norm):
            issues.append(
                {
                    "field_id": field_id,
                    "severity": "warning",
                    "message": "数字形式が期待されます。",
                }
            )

        if ("電話" in fmt or "0xx" in fmt.lower()) and not PHONE_RE.fullmatch(norm):
            issues.append(
                {
                    "field_id": field_id,
                    "severity": "warning",
                    "message": "電話番号の形式を確認してください（例: 019-1234-5678）。",
                }
            )

        if ("郵便" in fmt or "〒" in fmt or "郵便番号" in fmt) and not POSTAL_RE.search(norm):
            issues.append(
                {
                    "field_id": field_id,
                    "severity": "warning",
                    "message": "郵便番号形式を確認してください（例: 123-4567）。",
                }
            )

        if ("yyyy" in fmt.lower() or "日付" in fmt or "和暦" in fmt) and not (
            ISO_RE.match(norm) or norm.startswith("令和")
        ):
            issues.append(
                {
                    "field_id": field_id,
                    "severity": "warning",
                    "message": "日付形式が不正です（YYYY-MM-DD または 令和X年Y月Z日）。",
                }
            )

    # Lightweight cross-checks by Field_ID naming convention.
    vehicle_count = None
    driver_count = None
    for field_id, answer in normalized_answers.items():
        value = answer.get("norm", "")
        if not value.isdigit():
            continue
        upper = field_id.upper()
        if "VEHICLE" in upper or "CAR" in upper or "車両" in upper:
            vehicle_count = int(value)
        if "DRIVER" in upper or "運転者" in upper:
            driver_count = int(value)

    if vehicle_count is not None and driver_count is not None and driver_count < vehicle_count:
        issues.append(
            {
                "field_id": "_cross_check",
                "severity": "warning",
                "message": "運転者数が車両数を下回っています。整合性を確認してください。",
            }
        )

    return issues
