from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SCHEMA_PATH = BASE_DIR / "schema.json"


@lru_cache(maxsize=1)
def load_schema(schema_path: Optional[str] = None) -> Dict[str, Any]:
    path = Path(schema_path) if schema_path else DEFAULT_SCHEMA_PATH
    if not path.exists():
        raise FileNotFoundError(f"schema file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "fields" not in data or not isinstance(data["fields"], list):
        raise ValueError("schema.json must contain a top-level 'fields' list")
    return data


def clear_schema_cache() -> None:
    load_schema.cache_clear()


def get_fields(schema_path: Optional[str] = None) -> List[Dict[str, Any]]:
    schema = load_schema(schema_path)
    return schema.get("fields", [])


def get_field_lookup(schema_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for field in get_fields(schema_path):
        field_id = str(field.get("field_id", "")).strip()
        if field_id:
            lookup[field_id] = field
    return lookup


def build_step_groups(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []

    for idx, field in enumerate(fields):
        step_key = str(field.get("step_key") or "").strip()
        step_title = str(field.get("step_title") or "").strip()

        if not step_key:
            step_key = f"{field.get('form_name', '')}:{field.get('sheet', '')}"
        if not step_title:
            step_title = str(field.get("sheet") or field.get("form_name") or f"Step {idx + 1}")

        if step_key not in groups:
            groups[step_key] = {"step_key": step_key, "step_title": step_title, "fields": []}
            order.append(step_key)
        groups[step_key]["fields"].append(field)

    # Keep MVP UX compact: prioritize up to first 3 groups for guided flow,
    # while still returning full schema for expandability.
    grouped = [groups[key] for key in order]
    return grouped
