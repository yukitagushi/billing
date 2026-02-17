#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"a": MAIN_NS, "r": REL_NS, "p": PKG_REL_NS}

CELL_REF_RE = re.compile(r"^([A-Z]+)(\d+)$")


def col_to_index(col_letters: str) -> int:
    value = 0
    for ch in col_letters:
        value = value * 26 + (ord(ch) - ord("A") + 1)
    return value


def parse_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: List[str] = []
    for si in root.findall("a:si", NS):
        text = "".join(t.text or "" for t in si.findall(".//a:t", NS))
        strings.append(text)
    return strings


def get_sheet_path(zf: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))

    rid_to_target: Dict[str, str] = {}
    for rel in rels.findall("p:Relationship", NS):
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target", "")
        if rid:
            rid_to_target[rid] = target

    for sheet in workbook.findall("a:sheets/a:sheet", NS):
        if sheet.attrib.get("name") == sheet_name:
            rid = sheet.attrib.get(f"{{{REL_NS}}}id")
            if not rid:
                break
            target = rid_to_target.get(rid, "")
            target = target.lstrip("/")
            if target.startswith("xl/"):
                return target
            return f"xl/{target}"

    available = [s.attrib.get("name", "") for s in workbook.findall("a:sheets/a:sheet", NS)]
    raise ValueError(f"sheet '{sheet_name}' not found. available={available}")


def parse_cell_value(cell: ET.Element, shared_strings: List[str]) -> str:
    cell_type = cell.attrib.get("t")

    if cell_type == "inlineStr":
        inline = cell.find("a:is", NS)
        if inline is None:
            return ""
        return "".join(t.text or "" for t in inline.findall(".//a:t", NS))

    v = cell.find("a:v", NS)
    if v is None:
        return ""

    raw = v.text or ""
    if cell_type == "s":
        if raw.isdigit():
            idx = int(raw)
            if 0 <= idx < len(shared_strings):
                return shared_strings[idx]
        return raw

    return raw


def parse_rows(zf: zipfile.ZipFile, sheet_path: str) -> List[Dict[int, str]]:
    root = ET.fromstring(zf.read(sheet_path))
    sheet_data = root.find("a:sheetData", NS)
    if sheet_data is None:
        return []

    shared_strings = parse_shared_strings(zf)
    rows: List[Dict[int, str]] = []

    for row in sheet_data.findall("a:row", NS):
        row_values: Dict[int, str] = {}
        for cell in row.findall("a:c", NS):
            ref = cell.attrib.get("r", "")
            m = CELL_REF_RE.match(ref)
            if not m:
                continue
            col_idx = col_to_index(m.group(1))
            row_values[col_idx] = parse_cell_value(cell, shared_strings)
        rows.append(row_values)

    return rows


def normalize_required(value: str) -> bool:
    lowered = (value or "").strip().lower()
    if lowered in {"true", "1", "yes", "required", "必須"}:
        return True
    return "必須" in (value or "")


def infer_step(field_id: str, item_name: str, question: str, form_name: str, form_file: str) -> Tuple[str, str]:
    text = " ".join([field_id, item_name, question, form_name, form_file])

    if field_id.upper().startswith("RATE"):
        return "step_3", "運賃・料金"

    if any(k in text for k in ["申請者", "代表", "会社", "法人", "住所", "氏名", "本店", "連絡先"]):
        return "step_1", "申請者情報"

    if any(k in text for k in ["営業所", "車庫", "休憩", "睡眠", "車両", "自動車", "配置"]):
        return "step_2", "営業所・車両"

    if any(k in text for k in ["運行管理", "整備管理", "運転者", "資金", "運賃", "料金", "収支"]):
        return "step_3", "人員・資金・運賃"

    # Fallback keeps the 3-step MVP structure.
    return "step_3", "人員・資金・運賃"


def build_fields(records: List[Dict[str, str]]) -> List[Dict[str, object]]:
    fields: List[Dict[str, object]] = []
    for record in records:
        field_id = (record.get("Field_ID") or "").strip()
        if not field_id:
            continue

        form_file = (record.get("Form_File") or "").strip()
        form_name = (record.get("Form_Name") or "").strip()
        sheet = (record.get("Sheet") or "").strip()
        item_name = (record.get("Item_Name") or "").strip()
        question = (record.get("Question") or "").strip()

        step_key, step_title = infer_step(field_id, item_name, question, form_name, form_file)

        fields.append(
            {
                "form_file": form_file,
                "form_name": form_name,
                "sheet": sheet,
                "cell_range": (record.get("Cell_Range") or "").strip(),
                "field_id": field_id,
                "item_name": item_name,
                "question": question,
                "help": question,
                "example": (record.get("Example") or "").strip(),
                "format": (record.get("Format") or "").strip(),
                "required": normalize_required(record.get("Required") or ""),
                "evidence": (record.get("Evidence") or "").strip(),
                "what_to_fill": (record.get("What_to_Fill") or "").strip(),
                "step_key": step_key,
                "step_title": step_title,
            }
        )

    return fields


def extract_schema(src: Path, sheet_name: str, out: Path) -> int:
    with zipfile.ZipFile(src) as zf:
        sheet_path = get_sheet_path(zf, sheet_name)
        rows = parse_rows(zf, sheet_path)

    if not rows:
        raise ValueError("sheet has no rows")

    header_row = rows[0]
    headers = {idx: value.strip() for idx, value in header_row.items() if value.strip()}
    if not headers:
        raise ValueError("header row is empty")

    records: List[Dict[str, str]] = []
    for row in rows[1:]:
        record: Dict[str, str] = {}
        for idx, header in headers.items():
            record[header] = row.get(idx, "")
        if any(v.strip() for v in record.values()):
            records.append(record)

    fields = build_fields(records)
    payload = {
        "meta": {
            "source": str(src),
            "sheet": sheet_name,
            "field_count": len(fields),
        },
        "fields": fields,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return len(fields)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract schema.json from questionnaire xlsx")
    parser.add_argument(
        "--src",
        default="../templates/iwate_iwaizumi_ai_input_questionnaire.xlsx",
        help="source questionnaire xlsx path",
    )
    parser.add_argument("--sheet", default="01_入力項目一覧", help="sheet name")
    parser.add_argument("--out", default="../app/schema.json", help="output schema.json path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base = Path(__file__).resolve().parent
    src = (base / args.src).resolve()
    out = (base / args.out).resolve()

    count = extract_schema(src=src, sheet_name=args.sheet, out=out)
    print(f"OK: {count} fields -> {out}")


if __name__ == "__main__":
    main()
