from __future__ import annotations

import hashlib
import json
import os
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .db import (
    create_case,
    get_answers,
    get_case,
    init_db,
    list_cases,
    list_exports,
    save_export,
    upsert_answers,
)
from .excel_writer import create_review_report, write_templates
from .normalizer import normalize_answers
from .schema_loader import build_step_groups, get_field_lookup, get_fields
from .validator import validate_answers

APP_DIR = Path(__file__).resolve().parent
SERVICE_DIR = APP_DIR.parent
TEMPLATE_DIR = SERVICE_DIR / "templates"
if os.getenv("EXCEL_FILLER_EXPORT_DIR"):
    EXPORT_DIR = Path(os.environ["EXCEL_FILLER_EXPORT_DIR"])
elif os.getenv("VERCEL"):
    EXPORT_DIR = Path("/tmp/green-permit-intake/exports")
else:
    EXPORT_DIR = SERVICE_DIR / "exports"
MAPPING_PATH = APP_DIR / "mapping.yml"
SCHEMA_PATH = APP_DIR / "schema.json"


class CreateCaseRequest(BaseModel):
    title: str = "新規案件"


class AnswersUpdateRequest(BaseModel):
    answers: Dict[str, Any] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    include_debug_json: bool = True


app = FastAPI(title="Green Permit Intake Export API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/schema")
def schema() -> Dict[str, Any]:
    fields = get_fields(str(SCHEMA_PATH))
    steps = build_step_groups(fields)
    return {
        "field_count": len(fields),
        "steps": [
            {
                "step_key": step["step_key"],
                "step_title": step["step_title"],
                "field_count": len(step["fields"]),
            }
            for step in steps
        ],
        "fields": fields,
    }


@app.get("/cases")
def cases(limit: int = 50) -> Dict[str, Any]:
    return {"cases": list_cases(limit=limit)}


@app.post("/cases")
def create_case_endpoint(payload: CreateCaseRequest) -> Dict[str, Any]:
    case_id = str(uuid.uuid4())
    case = create_case(case_id, payload.title.strip() or "新規案件")
    return {"case": case}


@app.get("/cases/{case_id}")
def get_case_endpoint(case_id: str) -> Dict[str, Any]:
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")

    raw_answers = get_answers(case_id, normalized=False)
    norm_answers = get_answers(case_id, normalized=True)
    exports = list_exports(case_id)

    return {
        "case": case,
        "answers_raw": raw_answers,
        "answers_norm": norm_answers,
        "exports": exports,
    }


@app.put("/cases/{case_id}/answers")
def update_answers_endpoint(case_id: str, payload: AnswersUpdateRequest) -> Dict[str, Any]:
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")

    field_lookup = get_field_lookup(str(SCHEMA_PATH))
    normalized = normalize_answers(payload.answers, field_lookup)
    updated = upsert_answers(case_id, normalized)

    fields = get_fields(str(SCHEMA_PATH))
    merged_raw = get_answers(case_id, normalized=False)
    merged_obj = normalize_answers(merged_raw, field_lookup)
    issues = validate_answers(fields, merged_obj)

    return {"updated": updated, "issues": issues}


@app.post("/cases/{case_id}/validate")
def validate_case_endpoint(case_id: str) -> Dict[str, Any]:
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")

    fields = get_fields(str(SCHEMA_PATH))
    raw_answers = get_answers(case_id, normalized=False)
    field_lookup = get_field_lookup(str(SCHEMA_PATH))
    normalized = normalize_answers(raw_answers, field_lookup)
    issues = validate_answers(fields, normalized)

    return {"issue_count": len(issues), "issues": issues}


@app.post("/exports/{case_id}")
def export_case_endpoint(case_id: str, payload: ExportRequest) -> FileResponse:
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")

    fields = get_fields(str(SCHEMA_PATH))
    field_lookup = get_field_lookup(str(SCHEMA_PATH))
    raw_answers = get_answers(case_id, normalized=False)
    normalized = normalize_answers(raw_answers, field_lookup)

    # Persist latest normalized answers before export.
    upsert_answers(case_id, normalized)

    validation_issues = validate_answers(fields, normalized)
    answers_norm = {field_id: payload["norm"] for field_id, payload in normalized.items()}

    export_id = str(uuid.uuid4())
    export_work_dir = EXPORT_DIR / case_id / export_id
    export_work_dir.mkdir(parents=True, exist_ok=True)

    write_result = write_templates(
        answers_norm=answers_norm,
        schema_lookup=field_lookup,
        template_dir=TEMPLATE_DIR,
        output_dir=export_work_dir,
        mapping_path=MAPPING_PATH,
    )

    review_path = create_review_report(
        out_path=export_work_dir / "review_report.xlsx",
        validation_issues=validation_issues,
        mapping_notes=write_result.mapping_notes,
    )

    if payload.include_debug_json:
        debug_path = export_work_dir / "debug_answers.json"
        with debug_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "case": case,
                    "answers_raw": raw_answers,
                    "answers_norm": answers_norm,
                    "validation_issues": validation_issues,
                    "mapping_notes": write_result.mapping_notes,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    zip_path = EXPORT_DIR / case_id / f"export_{export_id}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    files_to_zip: List[Path] = list(write_result.output_files) + [review_path]
    if payload.include_debug_json:
        files_to_zip.append(export_work_dir / "debug_answers.json")

    # If legacy .xls template exists but converted .xlsx is absent, include original for traceability.
    legacy_xls = TEMPLATE_DIR / "001388356.xls"
    converted = TEMPLATE_DIR / "001388356_converted.xlsx"
    if legacy_xls.exists() and not converted.exists():
        files_to_zip.append(legacy_xls)

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files_to_zip:
            if file_path.exists():
                zf.write(file_path, arcname=file_path.name)

    checksum = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    save_export(export_id, case_id, str(zip_path), checksum)

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=zip_path.name,
    )
