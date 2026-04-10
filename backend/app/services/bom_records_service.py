from __future__ import annotations

import hashlib
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException

try:
    import psycopg
except ImportError:
    psycopg = None

from app.config import (
    ALLOWED_EXTENSIONS,
    ALLOWED_SAVE_FILE_EXTENSIONS,
    FILE_STORAGE_DIR,
    MAX_UPLOAD_BYTES,
)
from app.db import get_db_connection, require_psycopg
from app.services.bom_utils import (
    guess_mime_type,
    normalize_record_id,
    normalize_text,
    safe_filename,
    status_from_flags,
)

logger = logging.getLogger("bom_api")


def init_persistence_layer() -> None:
    require_psycopg()
    FILE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DO $$
                BEGIN
                    IF to_regclass('public.bom_saved_records') IS NULL
                       AND to_regclass('public.bom_save_records') IS NOT NULL THEN
                        ALTER TABLE bom_save_records RENAME TO bom_saved_records;
                    END IF;
                END $$;
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bom_saved_records (
                    record_id UUID PRIMARY KEY,
                    status VARCHAR(32) NOT NULL DEFAULT 'draft',
                    file_saved BOOLEAN NOT NULL DEFAULT FALSE,
                    metadata_saved BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bom_saved_files (
                    record_id UUID PRIMARY KEY REFERENCES bom_saved_records(record_id) ON DELETE CASCADE,
                    original_file_name TEXT NOT NULL,
                    stored_file_name TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    file_size BIGINT NOT NULL,
                    file_sha256 TEXT NOT NULL,
                    saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                ALTER TABLE bom_saved_files
                ADD COLUMN IF NOT EXISTS file_content BYTEA;
                """
            )
            cur.execute(
                """
                ALTER TABLE bom_saved_files
                ADD COLUMN IF NOT EXISTS file_mime_type TEXT;
                """
            )
            cur.execute(
                """
                ALTER TABLE bom_saved_files
                ADD COLUMN IF NOT EXISTS storage_backend VARCHAR(16) NOT NULL DEFAULT 'filesystem';
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bom_saved_metadata (
                    record_id UUID PRIMARY KEY REFERENCES bom_saved_records(record_id) ON DELETE CASCADE,
                    file_name TEXT NOT NULL,
                    upload_date TEXT NOT NULL,
                    version TEXT NOT NULL,
                    saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bom_saved_tables (
                    record_id UUID PRIMARY KEY REFERENCES bom_saved_records(record_id) ON DELETE CASCADE,
                    source_file_name TEXT NOT NULL,
                    source_extension VARCHAR(16) NOT NULL,
                    row_count INTEGER NOT NULL,
                    columns_json JSONB NOT NULL,
                    rows_json JSONB NOT NULL,
                    saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
        conn.commit()


def _fetch_record_for_update(cur, record_id: str) -> dict[str, Any]:
    cur.execute(
        """
        SELECT record_id, status, file_saved, metadata_saved
        FROM bom_saved_records
        WHERE record_id = %s
        FOR UPDATE;
        """,
        (record_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="record_id not found.")
    return row


def save_uploaded_bom_table(
    file_name: str,
    extension: str,
    columns: list[str],
    rows: list[dict[str, Any]],
    record_id: str | None = None,
) -> dict[str, Any]:
    normalized_extension = str(extension or "").lower()
    if normalized_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .csv and .xlsx files are supported.")

    source_file_name = safe_filename(file_name)
    normalized_columns = [str(col) for col in (columns or [])]
    row_count = len(rows)
    columns_json = json.dumps(normalized_columns, ensure_ascii=False, default=str)
    rows_json = json.dumps(rows, ensure_ascii=False, default=str)

    normalized_record_id = normalize_record_id(record_id) if record_id else str(uuid.uuid4())

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if record_id:
                existing = _fetch_record_for_update(cur, normalized_record_id)
                save_state = {
                    "status": existing["status"],
                    "file_saved": bool(existing["file_saved"]),
                    "metadata_saved": bool(existing["metadata_saved"]),
                }
            else:
                cur.execute(
                    """
                    INSERT INTO bom_saved_records (record_id, status, file_saved, metadata_saved)
                    VALUES (%s, 'draft', FALSE, FALSE);
                    """,
                    (normalized_record_id,),
                )
                save_state = {
                    "status": "draft",
                    "file_saved": False,
                    "metadata_saved": False,
                }

            cur.execute(
                """
                INSERT INTO bom_saved_tables (
                    record_id,
                    source_file_name,
                    source_extension,
                    row_count,
                    columns_json,
                    rows_json
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)
                ON CONFLICT (record_id)
                DO UPDATE SET
                    source_file_name = EXCLUDED.source_file_name,
                    source_extension = EXCLUDED.source_extension,
                    row_count = EXCLUDED.row_count,
                    columns_json = EXCLUDED.columns_json,
                    rows_json = EXCLUDED.rows_json,
                    updated_at = NOW();
                """,
                (
                    normalized_record_id,
                    source_file_name,
                    normalized_extension,
                    row_count,
                    columns_json,
                    rows_json,
                ),
            )

            cur.execute(
                """
                UPDATE bom_saved_records
                SET updated_at = NOW()
                WHERE record_id = %s;
                """,
                (normalized_record_id,),
            )
        conn.commit()

    return {
        "record_id": normalized_record_id,
        "save_state": save_state,
        "table_state": {
            "row_count": row_count,
            "column_count": len(normalized_columns),
            "source_file_name": source_file_name,
            "source_extension": normalized_extension,
        },
    }


def create_new_save_record() -> dict[str, Any]:
    record_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bom_saved_records (record_id, status, file_saved, metadata_saved)
                VALUES (%s, 'draft', FALSE, FALSE);
                """,
                (record_id,),
            )
        conn.commit()

    return {
        "record_id": record_id,
        "save_state": {
            "status": "draft",
            "file_saved": False,
            "metadata_saved": False,
        },
    }


def save_file_record(record_id: str, file_name: str, contents: bytes, mime_type: str | None = None) -> dict[str, Any]:
    require_psycopg()

    normalized_record_id = normalize_record_id(record_id)
    original_file_name = safe_filename(file_name)
    extension = Path(original_file_name).suffix.lower()

    if extension not in ALLOWED_SAVE_FILE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .xlsx and .csv files can be stored.")
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Max allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    stored_file_name = f"source{extension}"
    virtual_stored_path = f"database://bom_saved_files/{normalized_record_id}/{stored_file_name}"
    file_sha256 = hashlib.sha256(contents).hexdigest()
    resolved_mime_type = guess_mime_type(original_file_name, mime_type)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            row = _fetch_record_for_update(cur, normalized_record_id)
            metadata_saved = bool(row["metadata_saved"])
            status = status_from_flags(True, metadata_saved)

            cur.execute(
                """
                INSERT INTO bom_saved_files (
                    record_id,
                    original_file_name,
                    stored_file_name,
                    stored_path,
                    file_size,
                    file_sha256,
                    file_content,
                    file_mime_type,
                    storage_backend
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'database')
                ON CONFLICT (record_id)
                DO UPDATE SET
                    original_file_name = EXCLUDED.original_file_name,
                    stored_file_name = EXCLUDED.stored_file_name,
                    stored_path = EXCLUDED.stored_path,
                    file_size = EXCLUDED.file_size,
                    file_sha256 = EXCLUDED.file_sha256,
                    file_content = EXCLUDED.file_content,
                    file_mime_type = EXCLUDED.file_mime_type,
                    storage_backend = EXCLUDED.storage_backend,
                    updated_at = NOW();
                """,
                (
                    normalized_record_id,
                    original_file_name,
                    stored_file_name,
                    virtual_stored_path,
                    len(contents),
                    file_sha256,
                    psycopg.Binary(contents),
                    resolved_mime_type,
                ),
            )

            cur.execute(
                """
                UPDATE bom_saved_records
                SET file_saved = TRUE,
                    metadata_saved = %s,
                    status = %s,
                    updated_at = NOW()
                WHERE record_id = %s;
                """,
                (metadata_saved, status, normalized_record_id),
            )
        conn.commit()

    return {
        "record_id": normalized_record_id,
        "save_state": {
            "status": status,
            "file_saved": True,
            "metadata_saved": metadata_saved,
        },
    }


def save_metadata_record(record_id: str, file_name: str, upload_date: str, version: str) -> dict[str, Any]:
    normalized_record_id = normalize_record_id(record_id)
    normalized_file_name = normalize_text(file_name, "file_name")
    normalized_upload_date = normalize_text(upload_date, "upload_date")
    normalized_version = normalize_text(version, "version")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            row = _fetch_record_for_update(cur, normalized_record_id)
            file_saved = bool(row["file_saved"])
            status = status_from_flags(file_saved, True)

            cur.execute(
                """
                INSERT INTO bom_saved_metadata (record_id, file_name, upload_date, version)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (record_id)
                DO UPDATE SET
                    file_name = EXCLUDED.file_name,
                    upload_date = EXCLUDED.upload_date,
                    version = EXCLUDED.version,
                    updated_at = NOW();
                """,
                (
                    normalized_record_id,
                    normalized_file_name,
                    normalized_upload_date,
                    normalized_version,
                ),
            )

            cur.execute(
                """
                UPDATE bom_saved_records
                SET file_saved = %s,
                    metadata_saved = TRUE,
                    status = %s,
                    updated_at = NOW()
                WHERE record_id = %s;
                """,
                (file_saved, status, normalized_record_id),
            )
        conn.commit()

    return {
        "record_id": normalized_record_id,
        "save_state": {
            "status": status,
            "file_saved": file_saved,
            "metadata_saved": True,
        },
    }


def save_file_and_metadata_record(
    record_id: str,
    file_name: str,
    upload_date: str,
    version: str,
    upload_file_name: str,
    contents: bytes,
    mime_type: str | None = None,
) -> dict[str, Any]:
    require_psycopg()

    normalized_record_id = normalize_record_id(record_id)
    normalized_file_name = normalize_text(file_name, "file_name")
    normalized_upload_date = normalize_text(upload_date, "upload_date")
    normalized_version = normalize_text(version, "version")

    original_file_name = safe_filename(upload_file_name)
    extension = Path(original_file_name).suffix.lower()
    if extension not in ALLOWED_SAVE_FILE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .xlsx and .csv files can be stored.")
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Max allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    stored_file_name = f"source{extension}"
    virtual_stored_path = f"database://bom_saved_files/{normalized_record_id}/{stored_file_name}"
    file_sha256 = hashlib.sha256(contents).hexdigest()
    resolved_mime_type = guess_mime_type(original_file_name, mime_type)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            _fetch_record_for_update(cur, normalized_record_id)

            cur.execute(
                """
                INSERT INTO bom_saved_files (
                    record_id,
                    original_file_name,
                    stored_file_name,
                    stored_path,
                    file_size,
                    file_sha256,
                    file_content,
                    file_mime_type,
                    storage_backend
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'database')
                ON CONFLICT (record_id)
                DO UPDATE SET
                    original_file_name = EXCLUDED.original_file_name,
                    stored_file_name = EXCLUDED.stored_file_name,
                    stored_path = EXCLUDED.stored_path,
                    file_size = EXCLUDED.file_size,
                    file_sha256 = EXCLUDED.file_sha256,
                    file_content = EXCLUDED.file_content,
                    file_mime_type = EXCLUDED.file_mime_type,
                    storage_backend = EXCLUDED.storage_backend,
                    updated_at = NOW();
                """,
                (
                    normalized_record_id,
                    original_file_name,
                    stored_file_name,
                    virtual_stored_path,
                    len(contents),
                    file_sha256,
                    psycopg.Binary(contents),
                    resolved_mime_type,
                ),
            )

            cur.execute(
                """
                INSERT INTO bom_saved_metadata (record_id, file_name, upload_date, version)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (record_id)
                DO UPDATE SET
                    file_name = EXCLUDED.file_name,
                    upload_date = EXCLUDED.upload_date,
                    version = EXCLUDED.version,
                    updated_at = NOW();
                """,
                (
                    normalized_record_id,
                    normalized_file_name,
                    normalized_upload_date,
                    normalized_version,
                ),
            )

            cur.execute(
                """
                UPDATE bom_saved_records
                SET file_saved = TRUE,
                    metadata_saved = TRUE,
                    status = 'paired',
                    updated_at = NOW()
                WHERE record_id = %s;
                """,
                (normalized_record_id,),
            )
        conn.commit()

    return {
        "record_id": normalized_record_id,
        "save_state": {
            "status": "paired",
            "file_saved": True,
            "metadata_saved": True,
        },
    }


def delete_save_record(record_id: str) -> None:
    normalized_record_id = normalize_record_id(record_id)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bom_saved_records WHERE record_id = %s", (normalized_record_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="record_id not found.")
        conn.commit()


def list_save_records(limit: int) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    r.record_id,
                    r.status,
                    r.file_saved,
                    r.metadata_saved,
                    r.created_at,
                    r.updated_at,
                    m.file_name,
                    m.upload_date,
                    m.version,
                    f.original_file_name,
                    f.file_size,
                    f.storage_backend,
                    f.saved_at AS file_saved_at,
                    m.saved_at AS metadata_saved_at,
                    t.source_file_name AS uploaded_source_file_name,
                    t.source_extension,
                    t.row_count AS bom_row_count,
                    t.saved_at AS table_saved_at
                FROM bom_saved_records r
                LEFT JOIN bom_saved_metadata m ON m.record_id = r.record_id
                LEFT JOIN bom_saved_files f ON f.record_id = r.record_id
                LEFT JOIN bom_saved_tables t ON t.record_id = r.record_id
                ORDER BY r.updated_at DESC
                LIMIT %s;
                """,
                (limit,),
            )
            return cur.fetchall()


def read_saved_file_from_database(record_id: str) -> dict[str, Any]:
    normalized_record_id = normalize_record_id(record_id)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    record_id,
                    original_file_name,
                    stored_file_name,
                    stored_path,
                    file_content,
                    file_mime_type,
                    file_size,
                    storage_backend
                FROM bom_saved_files
                WHERE record_id = %s;
                """,
                (normalized_record_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Saved BOM file not found for record_id.")

    db_bytes = row.get("file_content")
    if isinstance(db_bytes, memoryview):
        db_bytes = db_bytes.tobytes()
    if isinstance(db_bytes, bytes) and db_bytes:
        return {
            "record_id": normalized_record_id,
            "content": db_bytes,
            "file_name": row.get("original_file_name") or row.get("stored_file_name") or "source.xlsx",
            "mime_type": guess_mime_type(row.get("original_file_name"), row.get("file_mime_type")),
            "storage_backend": row.get("storage_backend") or "database",
            "file_size": int(row.get("file_size") or len(db_bytes)),
        }

    legacy_path = row.get("stored_path") or ""
    legacy_file = Path(str(legacy_path))
    if legacy_file.exists() and legacy_file.is_file():
        content = legacy_file.read_bytes()
        return {
            "record_id": normalized_record_id,
            "content": content,
            "file_name": row.get("original_file_name") or legacy_file.name,
            "mime_type": guess_mime_type(row.get("original_file_name"), row.get("file_mime_type")),
            "storage_backend": "filesystem",
            "file_size": len(content),
        }

    raise HTTPException(status_code=404, detail="Saved BOM file content is missing.")


def get_saved_bom_table(record_id: str, offset: int, limit: int) -> dict[str, Any]:
    normalized_record_id = normalize_record_id(record_id)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    t.record_id,
                    t.source_file_name,
                    t.source_extension,
                    t.row_count,
                    t.columns_json,
                    t.rows_json,
                    t.saved_at,
                    t.updated_at,
                    r.status,
                    r.file_saved,
                    r.metadata_saved
                FROM bom_saved_tables t
                JOIN bom_saved_records r ON r.record_id = t.record_id
                WHERE t.record_id = %s;
                """,
                (normalized_record_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Saved BOM table not found for record_id.")

    all_rows = row.get("rows_json") or []
    if not isinstance(all_rows, list):
        all_rows = []

    start = max(0, int(offset))
    size = max(1, int(limit))
    end = start + size
    sliced_rows = all_rows[start:end]

    return {
        "record_id": row["record_id"],
        "save_state": {
            "status": row["status"],
            "file_saved": bool(row["file_saved"]),
            "metadata_saved": bool(row["metadata_saved"]),
        },
        "table_state": {
            "source_file_name": row["source_file_name"],
            "source_extension": row["source_extension"],
            "row_count": int(row["row_count"] or 0),
            "column_count": len(row.get("columns_json") or []),
            "saved_at": row["saved_at"],
            "updated_at": row["updated_at"],
        },
        "columns": row.get("columns_json") or [],
        "rows": sliced_rows,
        "pagination": {
            "offset": start,
            "limit": size,
            "returned_rows": len(sliced_rows),
            "total_rows": int(row["row_count"] or 0),
            "has_more": end < int(row["row_count"] or 0),
        },
    }
