from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .settings import Settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(settings: Settings) -> None:
    settings.ensure_dirs()
    with connect(settings.db_path) as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY,
              job_type TEXT NOT NULL,
              status TEXT NOT NULL,
              agency TEXT NOT NULL DEFAULT 'default',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              started_at TEXT,
              completed_at TEXT,
              upload_dir TEXT NOT NULL,
              workspace_dir TEXT,
              original_filenames_json TEXT NOT NULL,
              manifest_path TEXT,
              validation_path TEXT,
              artifacts_json TEXT NOT NULL DEFAULT '[]',
              result_json TEXT,
              error_text TEXT,
              log_text TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_status_created
              ON jobs(status, created_at);
            """
        )
        conn.commit()


def create_job(
    settings: Settings,
    *,
    job_type: str,
    agency: str,
    upload_dir: Path,
    original_filenames: list[str],
) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    now = utc_now()
    row = {
        "id": job_id,
        "job_type": job_type,
        "status": "queued",
        "agency": agency,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "upload_dir": str(upload_dir),
        "workspace_dir": None,
        "original_filenames_json": json.dumps(original_filenames),
        "manifest_path": None,
        "validation_path": None,
        "artifacts_json": "[]",
        "result_json": None,
        "error_text": None,
        "log_text": "",
    }
    with connect(settings.db_path) as conn:
        conn.execute(
            """
            INSERT INTO jobs (
              id, job_type, status, agency, created_at, updated_at,
              started_at, completed_at, upload_dir, workspace_dir,
              original_filenames_json, manifest_path, validation_path,
              artifacts_json, result_json, error_text, log_text
            ) VALUES (
              :id, :job_type, :status, :agency, :created_at, :updated_at,
              :started_at, :completed_at, :upload_dir, :workspace_dir,
              :original_filenames_json, :manifest_path, :validation_path,
              :artifacts_json, :result_json, :error_text, :log_text
            )
            """,
            row,
        )
        conn.commit()
    return get_job(settings, job_id)


def _decode_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["original_filenames"] = json.loads(data.pop("original_filenames_json") or "[]")
    data["artifacts"] = json.loads(data.pop("artifacts_json") or "[]")
    data["result"] = json.loads(data["result_json"]) if data.get("result_json") else None
    return data


def get_job(settings: Settings, job_id: str) -> dict[str, Any] | None:
    with connect(settings.db_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _decode_row(row)


def update_job(settings: Settings, job_id: str, **fields: Any) -> dict[str, Any] | None:
    if not fields:
        return get_job(settings, job_id)
    fields["updated_at"] = utc_now()
    columns = ", ".join(f"{key} = :{key}" for key in fields)
    params = dict(fields)
    params["id"] = job_id
    with connect(settings.db_path) as conn:
        conn.execute(f"UPDATE jobs SET {columns} WHERE id = :id", params)
        conn.commit()
    return get_job(settings, job_id)


def claim_next_job(settings: Settings) -> dict[str, Any] | None:
    with connect(settings.db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT id FROM jobs
            WHERE status = 'queued'
            ORDER BY created_at ASC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            conn.commit()
            return None
        started_at = utc_now()
        conn.execute(
            """
            UPDATE jobs
            SET status = 'running',
                started_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (started_at, started_at, row["id"]),
        )
        conn.commit()
    return get_job(settings, row["id"])

