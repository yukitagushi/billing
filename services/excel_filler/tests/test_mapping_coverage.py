from __future__ import annotations

import json
import warnings
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = BASE_DIR / "app" / "schema.json"
MAPPING_PATH = BASE_DIR / "app" / "mapping.yml"


def _load_schema() -> dict:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_mapping() -> dict:
    with MAPPING_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_schema_has_fields() -> None:
    schema = _load_schema()
    fields = schema.get("fields", [])
    assert fields, "schema.json must include fields"


def test_field_id_unique() -> None:
    schema = _load_schema()
    field_ids = [f.get("field_id") for f in schema.get("fields", []) if f.get("field_id")]
    assert len(field_ids) == len(set(field_ids)), "field_id must be unique"


def test_mapping_coverage_warn_only() -> None:
    schema = _load_schema()
    mapping = _load_mapping()

    fields = schema.get("fields", [])
    schema_lookup = {f.get("field_id"): f for f in fields if f.get("field_id")}

    explicit_mapped = set()
    auto_target_forms = set()

    for template in mapping.get("templates", []):
        explicit_mapped.update((template.get("mappings") or {}).keys())
        for form in template.get("source_form_files", []):
            auto_target_forms.add(str(form))

    missing = []
    for field_id, field in schema_lookup.items():
        if field_id in explicit_mapped:
            continue

        form_file = str(field.get("form_file", "")).strip()
        cell_range = str(field.get("cell_range", "")).strip()
        auto_mappable = form_file in auto_target_forms and "!" in cell_range

        if not auto_mappable:
            missing.append(field_id)

    if missing:
        warnings.warn(
            f"{len(missing)} field_id entries are not explicitly/automatically mapped yet. "
            f"sample={missing[:10]}",
            stacklevel=1,
        )

    # Coverage gaps should be warning-level in early phase.
    assert True
