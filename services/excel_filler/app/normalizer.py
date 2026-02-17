from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict

COMMA_RE = re.compile(r"[,，\s円¥]")
WAREKI_RE = re.compile(r"令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日")
ISO_RE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")


def _to_int_like(value: str) -> str:
    cleaned = COMMA_RE.sub("", value)
    if cleaned == "":
        return ""
    if not re.fullmatch(r"-?\d+", cleaned):
        return value
    return str(int(cleaned))


def _wareki_to_iso(value: str) -> str:
    match = WAREKI_RE.search(value)
    if not match:
        return value
    reiwa_year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    western = reiwa_year + 2018
    try:
        dt = date(western, month, day)
    except ValueError:
        return value
    return dt.isoformat()


def _iso_to_wareki(value: str) -> str:
    match = ISO_RE.match(value)
    if not match:
        return value
    y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
    try:
        _ = date(y, m, d)
    except ValueError:
        return value
    if y < 2019:
        return f"{y}年{m}月{d}日"
    return f"令和{y - 2018}年{m}月{d}日"


def normalize_value(raw_value: Any, fmt: str) -> str:
    if raw_value is None:
        return ""
    if isinstance(raw_value, (int, float)):
        raw = str(raw_value)
    else:
        raw = str(raw_value).strip()

    if raw == "":
        return ""

    fmt_lower = fmt.lower()

    if "yyyy" in fmt_lower or "日付" in fmt or "和暦" in fmt:
        if raw.startswith("令和"):
            return _wareki_to_iso(raw)
        if ISO_RE.match(raw):
            # Normalize zero padding.
            dt = datetime.strptime(raw.replace("/", "-"), "%Y-%m-%d")
            return dt.date().isoformat()
        return raw

    if "金額" in fmt or "currency" in fmt_lower:
        return _to_int_like(raw)

    if "数字" in fmt or "number" in fmt_lower:
        return _to_int_like(raw)

    if "checkbox" in fmt_lower:
        lowered = raw.lower()
        return "true" if lowered in {"1", "true", "yes", "on", "レ"} else "false"

    return raw


def to_excel_value(norm_value: str, value_type: str) -> Any:
    if norm_value == "":
        return ""

    value_type = (value_type or "text").lower()
    if value_type in {"text", "text_multiline"}:
        return norm_value
    if value_type in {"number", "currency"}:
        int_like = _to_int_like(norm_value)
        if re.fullmatch(r"-?\d+", int_like):
            return int(int_like)
        return norm_value
    if value_type == "checkbox":
        lowered = norm_value.lower()
        return "レ" if lowered in {"1", "true", "yes", "on", "レ"} else ""
    if value_type == "date_wareki":
        return _iso_to_wareki(norm_value)
    if value_type == "date_iso":
        if norm_value.startswith("令和"):
            return _wareki_to_iso(norm_value)
        return norm_value
    return norm_value


def normalize_answers(
    answers: Dict[str, Any],
    field_lookup: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, str]]:
    normalized: Dict[str, Dict[str, str]] = {}

    for field_id, raw_value in answers.items():
        field = field_lookup.get(field_id, {})
        fmt = str(field.get("format", ""))
        raw = "" if raw_value is None else str(raw_value).strip()
        norm = normalize_value(raw, fmt)
        normalized[field_id] = {"raw": raw, "norm": norm}

    return normalized
