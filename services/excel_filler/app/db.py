from __future__ import annotations

import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if os.getenv("EXCEL_FILLER_DATA_DIR"):
    DATA_DIR = Path(os.environ["EXCEL_FILLER_DATA_DIR"])
elif os.getenv("VERCEL"):
    DATA_DIR = Path("/tmp/green-permit-intake/data")
else:
    DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "app.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS case_answers (
                case_id TEXT NOT NULL,
                field_id TEXT NOT NULL,
                answer_raw TEXT,
                answer_norm TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(case_id, field_id),
                FOREIGN KEY(case_id) REFERENCES cases(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exports (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                zip_path TEXT NOT NULL,
                checksum TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def create_case(case_id: str, title: str) -> Dict[str, str]:
    now = utc_now()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO cases (id, title, status, created_at, updated_at) VALUES (?, ?, 'draft', ?, ?)",
            (case_id, title, now, now),
        )
        conn.commit()
        return {
            "id": case_id,
            "title": title,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        }
    finally:
        conn.close()


def get_case(case_id: str) -> Optional[Dict[str, str]]:
    conn = _connect()
    try:
        cur = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def list_cases(limit: int = 50) -> List[Dict[str, str]]:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT * FROM cases ORDER BY updated_at DESC LIMIT ?",
            (max(1, min(limit, 200)),),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def upsert_answers(case_id: str, normalized_answers: Dict[str, Dict[str, str]]) -> int:
    now = utc_now()
    conn = _connect()
    try:
        rows: Iterable[tuple] = [
            (case_id, field_id, payload.get("raw", ""), payload.get("norm", ""), now)
            for field_id, payload in normalized_answers.items()
        ]

        conn.executemany(
            """
            INSERT INTO case_answers (case_id, field_id, answer_raw, answer_norm, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(case_id, field_id)
            DO UPDATE SET
                answer_raw = excluded.answer_raw,
                answer_norm = excluded.answer_norm,
                updated_at = excluded.updated_at
            """,
            rows,
        )
        conn.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now, case_id))
        conn.commit()
        return len(normalized_answers)
    finally:
        conn.close()


def get_answers(case_id: str, normalized: bool = False) -> Dict[str, str]:
    column = "answer_norm" if normalized else "answer_raw"
    conn = _connect()
    try:
        cur = conn.execute(
            f"SELECT field_id, {column} AS value FROM case_answers WHERE case_id = ?",
            (case_id,),
        )
        return {row["field_id"]: row["value"] or "" for row in cur.fetchall()}
    finally:
        conn.close()


def save_export(export_id: str, case_id: str, zip_path: str, checksum: str) -> Dict[str, str]:
    now = utc_now()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO exports (id, case_id, zip_path, checksum, created_at) VALUES (?, ?, ?, ?, ?)",
            (export_id, case_id, zip_path, checksum, now),
        )
        conn.execute("UPDATE cases SET status = 'exported', updated_at = ? WHERE id = ?", (now, case_id))
        conn.commit()
        return {
            "id": export_id,
            "case_id": case_id,
            "zip_path": zip_path,
            "checksum": checksum,
            "created_at": now,
        }
    finally:
        conn.close()


def list_exports(case_id: str) -> List[Dict[str, str]]:
    conn = _connect()
    try:
        cur = conn.execute("SELECT * FROM exports WHERE case_id = ? ORDER BY created_at DESC", (case_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
