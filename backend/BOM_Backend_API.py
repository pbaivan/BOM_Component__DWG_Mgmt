from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
import pandas as pd
import numpy as np
import io
import json
import uvicorn
import asyncio
import logging
import mimetypes
import os
import hashlib
import uuid
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

if load_dotenv is not None:
    load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger("bom_api")

MAX_UPLOAD_BYTES = int(os.getenv("BOM_MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
ALLOWED_SAVE_FILE_EXTENSIONS = {".xlsx", ".csv"}
LOCAL_ORIGIN_REGEX = os.getenv(
    "BOM_ALLOWED_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
)
DATABASE_URL = os.getenv(
    "BOM_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/bom_platform",
)
FILE_STORAGE_DIR = Path(
    os.getenv(
        "BOM_FILE_STORAGE_DIR",
        str(Path(__file__).resolve().parent / "data" / "bom_files"),
    )
)


class MetadataSaveRequest(BaseModel):
    record_id: str
    file_name: str
    upload_date: str
    version: str


def _parse_bom_rows(contents: bytes, extension: str) -> tuple[list[str], list[dict]]:
    """Parse BOM content in a worker thread. Dynamically detects header row in Excel to avoid Unnamed columns."""
    stream = io.BytesIO(contents)

    def get_excel_col_name(n):
        res = ""
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            res = chr(65 + remainder) + res
        return res

    if extension == ".csv":
        df = pd.read_csv(stream, keep_default_na=False, na_filter=False)
    else:
        preview_df = pd.read_excel(stream, engine="openpyxl", header=None, nrows=40, keep_default_na=False, na_filter=False)
        best_header_idx = 0
        max_score = -1
        
        for idx, row in preview_df.iterrows():
            row_strs = [str(x).strip().upper() for x in row.values if str(x).strip()]
            score = len(row_strs)
            for kw in ["PARENT", "COMPONENT", "PART", "ITEM", "DESC", "LEVEL", "QTY", "QUANTITY"]:
                if any(kw in s for s in row_strs):
                    score += 15
            if score > max_score:
                max_score = score
                best_header_idx = idx

        stream.seek(0)
        df = pd.read_excel(
            stream,
            engine="openpyxl",
            header=best_header_idx,
            keep_default_na=False,
            na_filter=False,
        )

    final_cols = []
    seen = set()
    for i, col in enumerate(df.columns.tolist()):
        c_str = str(col).strip()
        excel_col_letter = get_excel_col_name(i + 1)
        
        if "Unnamed" in c_str or not c_str:
            c_str = f"column_{excel_col_letter}"
            
        # Make column unique
        base = c_str
        count = 1
        while c_str in seen:
            c_str = f"{base}_{count}"
            count += 1
        seen.add(c_str)
        final_cols.append(c_str)
        
    df.columns = final_cols

    # Clean the dataframe: Replace NaN, Infinity, and Excel error strings (e.g. #N/A) with empty string
    error_patterns = [r'^#N/A', r'^#DIV/0!', r'^#VALUE!', r'^#REF!', r'^#NAME\?', r'^#NUM!']
    df = df.replace(to_replace=error_patterns, value="", regex=True)
    df = df.replace([np.nan, float('inf'), float('-inf')], "")
    df = df.fillna("")

    # Drop entirely empty rows gracefully (since we used keep_default_na=False, empty is "")
    if not df.empty:
        mask = (df != "").any(axis=1)
        df = df.loc[mask]

    columns = final_cols
    rows = df.to_dict(orient="records")
    return columns, rows
def _normalize_text(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"{field_name} is required.")
    return normalized


def _normalize_record_id(record_id: str) -> str:
    try:
        return str(uuid.UUID(str(record_id).strip()))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid record_id.")


def _safe_filename(filename: str) -> str:
    safe_name = Path(str(filename or "")).name.strip()
    if not safe_name:
        return "source.xlsx"
    return safe_name.replace("/", "_").replace("\\", "_")


def _status_from_flags(file_saved: bool, metadata_saved: bool) -> str:
    if file_saved and metadata_saved:
        return "paired"
    if file_saved:
        return "file_saved"
    if metadata_saved:
        return "metadata_saved"
    return "draft"


def _guess_mime_type(file_name: str, fallback: str | None = None) -> str:
    guessed, _ = mimetypes.guess_type(str(file_name or ""))
    return guessed or fallback or "application/octet-stream"


def _require_psycopg() -> None:
    if psycopg is None:
        raise RuntimeError("psycopg is not installed. Install it with: pip install psycopg[binary]")


def _get_db_connection():
    _require_psycopg()
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def _init_persistence_layer() -> None:
    _require_psycopg()
    FILE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    with _get_db_connection() as conn:
        with conn.cursor() as cur:
            # Backward-compatible rename: old bom_save_records -> new bom_saved_records.
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
            # Migration-safe columns for true in-database file storage.
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


def _save_uploaded_bom_table(
    file_name: str,
    extension: str,
    columns: list[str],
    rows: list[dict[str, Any]],
    record_id: str | None = None,
) -> dict[str, Any]:
    normalized_extension = str(extension or "").lower()
    if normalized_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .csv and .xlsx files are supported.")

    source_file_name = _safe_filename(file_name)
    normalized_columns = [str(col) for col in (columns or [])]
    row_count = len(rows)
    columns_json = json.dumps(normalized_columns, ensure_ascii=False, default=str)
    rows_json = json.dumps(rows, ensure_ascii=False, default=str)

    normalized_record_id = _normalize_record_id(record_id) if record_id else str(uuid.uuid4())

    with _get_db_connection() as conn:
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


def _create_new_save_record() -> dict[str, Any]:
    record_id = str(uuid.uuid4())
    with _get_db_connection() as conn:
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


def _save_file_record(record_id: str, file_name: str, contents: bytes, mime_type: str | None = None) -> dict[str, Any]:
    normalized_record_id = _normalize_record_id(record_id)
    original_file_name = _safe_filename(file_name)
    extension = Path(original_file_name).suffix.lower()

    if extension not in ALLOWED_SAVE_FILE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .xlsx and .csv files can be stored.")
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File is too large. Max allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")

    stored_file_name = f"source{extension}"
    virtual_stored_path = f"database://bom_saved_files/{normalized_record_id}/{stored_file_name}"
    file_sha256 = hashlib.sha256(contents).hexdigest()
    resolved_mime_type = _guess_mime_type(original_file_name, mime_type)

    with _get_db_connection() as conn:
        with conn.cursor() as cur:
            row = _fetch_record_for_update(cur, normalized_record_id)
            metadata_saved = bool(row["metadata_saved"])
            status = _status_from_flags(True, metadata_saved)

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


def _save_metadata_record(record_id: str, file_name: str, upload_date: str, version: str) -> dict[str, Any]:
    normalized_record_id = _normalize_record_id(record_id)
    normalized_file_name = _normalize_text(file_name, "file_name")
    normalized_upload_date = _normalize_text(upload_date, "upload_date")
    normalized_version = _normalize_text(version, "version")

    with _get_db_connection() as conn:
        with conn.cursor() as cur:
            row = _fetch_record_for_update(cur, normalized_record_id)
            file_saved = bool(row["file_saved"])
            status = _status_from_flags(file_saved, True)

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


def _save_file_and_metadata_record(
    record_id: str,
    file_name: str,
    upload_date: str,
    version: str,
    upload_file_name: str,
    contents: bytes,
    mime_type: str | None = None,
) -> dict[str, Any]:
    normalized_record_id = _normalize_record_id(record_id)
    normalized_file_name = _normalize_text(file_name, "file_name")
    normalized_upload_date = _normalize_text(upload_date, "upload_date")
    normalized_version = _normalize_text(version, "version")

    original_file_name = _safe_filename(upload_file_name)
    extension = Path(original_file_name).suffix.lower()
    if extension not in ALLOWED_SAVE_FILE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .xlsx and .csv files can be stored.")
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File is too large. Max allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")

    stored_file_name = f"source{extension}"
    virtual_stored_path = f"database://bom_saved_files/{normalized_record_id}/{stored_file_name}"
    file_sha256 = hashlib.sha256(contents).hexdigest()
    resolved_mime_type = _guess_mime_type(original_file_name, mime_type)

    with _get_db_connection() as conn:
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



def _delete_save_record(record_id: str) -> None:
    normalized_record_id = _normalize_record_id(record_id)
    with _get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bom_saved_records WHERE record_id = %s", (normalized_record_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="record_id not found.")
        conn.commit()


def _list_save_records(limit: int) -> list[dict[str, Any]]:
    with _get_db_connection() as conn:
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


def _read_saved_file_from_database(record_id: str) -> dict[str, Any]:
    normalized_record_id = _normalize_record_id(record_id)

    with _get_db_connection() as conn:
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
            "mime_type": _guess_mime_type(row.get("original_file_name"), row.get("file_mime_type")),
            "storage_backend": row.get("storage_backend") or "database",
            "file_size": int(row.get("file_size") or len(db_bytes)),
        }

    # Fallback for legacy filesystem rows created before database blob support.
    legacy_path = row.get("stored_path") or ""
    legacy_file = Path(str(legacy_path))
    if legacy_file.exists() and legacy_file.is_file():
        content = legacy_file.read_bytes()
        return {
            "record_id": normalized_record_id,
            "content": content,
            "file_name": row.get("original_file_name") or legacy_file.name,
            "mime_type": _guess_mime_type(row.get("original_file_name"), row.get("file_mime_type")),
            "storage_backend": "filesystem",
            "file_size": len(content),
        }

    raise HTTPException(status_code=404, detail="Saved BOM file content is missing.")


def _get_saved_bom_table(record_id: str, offset: int, limit: int) -> dict[str, Any]:
    normalized_record_id = _normalize_record_id(record_id)

    with _get_db_connection() as conn:
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


def _get_allowed_origins() -> list[str]:
    raw = os.getenv("BOM_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

app = FastAPI(title="BOM Platform API (Mock Phase)")

# Configure CORS to allow React frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_origin_regex=LOCAL_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    try:
        await asyncio.to_thread(_init_persistence_layer)
        logger.info("Persistence layer initialized.")
    except Exception:
        logger.exception("Failed to initialize persistence layer.")
        raise


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": str(exc.detail)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, __: Exception):
    logger.exception("Unhandled server exception.")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error."},
    )


@app.get("/")
async def root():
    """Welcome page to verify server is running."""
    return {
        "message": "Success! BOM Backend is running.",
        "docs_url": "Visit /docs for API documentation"
    }


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "bom-backend",
    }


@app.post("/api/upload")
async def upload_bom(file: UploadFile = File(...), record_id: str | None = Form(default=None)):
    """Receive, parse, and extract data/columns from the uploaded Excel/CSV file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .csv and .xlsx files are supported.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File is too large. Max allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")

    try:
        columns, rows = await asyncio.to_thread(_parse_bom_rows, contents, extension)
    except HTTPException:
        raise
    except (ValueError, pd.errors.ParserError, UnicodeDecodeError):
        logger.warning("Upload rejected due to invalid file format: %s", file.filename)
        raise HTTPException(status_code=400, detail="Invalid or corrupted BOM file format.")
    except Exception:
        logger.exception("Unexpected error while processing upload parse step.")
        raise HTTPException(status_code=500, detail="Failed to process BOM file.")

    try:
        persistence_result = await asyncio.to_thread(
            _save_uploaded_bom_table,
            file.filename,
            extension,
            columns,
            rows,
            record_id,
        )
        file_result = await asyncio.to_thread(
            _save_file_record,
            persistence_result["record_id"],
            file.filename,
            contents,
            file.content_type,
        )
        return {
            "status": "success",
            "rows": len(rows),
            "columns": columns,
            "data": rows,
            "record_id": persistence_result["record_id"],
            "save_state": file_result["save_state"],
            "table_state": persistence_result["table_state"],
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to persist uploaded BOM table data.")
        raise HTTPException(status_code=500, detail="Failed to persist uploaded BOM table data.")


@app.post("/api/save/new-record")
async def create_save_record():
    try:
        result = await asyncio.to_thread(_create_new_save_record)
        return {
            "status": "success",
            "message": "Save record created.",
            **result,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create save record.")
        raise HTTPException(status_code=500, detail="Failed to create save record.")


@app.post("/api/save/file")
async def save_bom_file(record_id: str = Form(...), file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    contents = await file.read()

    try:
        result = await asyncio.to_thread(_save_file_record, record_id, file.filename, contents, file.content_type)
        return {
            "status": "success",
            "message": "BOM file saved.",
            **result,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to save BOM file.")
        raise HTTPException(status_code=500, detail="Failed to save BOM file.")


@app.post("/api/save/metadata")
async def save_bom_metadata(payload: MetadataSaveRequest):
    try:
        result = await asyncio.to_thread(
            _save_metadata_record,
            payload.record_id,
            payload.file_name,
            payload.upload_date,
            payload.version,
        )
        return {
            "status": "success",
            "message": "BOM metadata saved.",
            **result,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to save BOM metadata.")
        raise HTTPException(status_code=500, detail="Failed to save BOM metadata.")


@app.post("/api/save/both")
async def save_bom_file_and_metadata(
    record_id: str = Form(...),
    file_name: str = Form(...),
    upload_date: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    contents = await file.read()

    try:
        result = await asyncio.to_thread(
            _save_file_and_metadata_record,
            record_id,
            file_name,
            upload_date,
            version,
            file.filename,
            contents,
            file.content_type,
        )
        return {
            "status": "success",
            "message": "BOM file and metadata saved.",
            **result,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to save BOM file and metadata.")
        raise HTTPException(status_code=500, detail="Failed to save BOM file and metadata.")



@app.delete("/api/save/record/{record_id}")
async def delete_save_record(record_id: str):
    try:
        await asyncio.to_thread(_delete_save_record, record_id)
        return {
            "status": "success",
            "message": "BOM record and all associated tables have been permanently deleted.",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete the BOM record.")
        raise HTTPException(status_code=500, detail="Failed to delete the BOM record.")

@app.get("/api/save/list")
async def list_save_records(limit: int = Query(default=50, ge=1, le=200)):
    try:
        records = await asyncio.to_thread(_list_save_records, limit)
        return {
            "status": "success",
            "records": records,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to list save records.")
        raise HTTPException(status_code=500, detail="Failed to list save records.")


@app.get("/api/save/table/{record_id}")
async def get_saved_bom_table(record_id: str, offset: int = Query(default=0, ge=0), limit: int = Query(default=100000, ge=1)):
    try:
        result = await asyncio.to_thread(_get_saved_bom_table, record_id, offset, limit)
        return {
            "status": "success",
            **result,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch saved BOM table data.")
        raise HTTPException(status_code=500, detail="Failed to fetch saved BOM table data.")


@app.get("/api/save/file/{record_id}/download")
async def download_saved_bom_file(record_id: str):
    try:
        file_record = await asyncio.to_thread(_read_saved_file_from_database, record_id)
        safe_file_name = _safe_filename(file_record["file_name"])
        return Response(
            content=file_record["content"],
            media_type=file_record["mime_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{safe_file_name}"',
                "X-BOM-Storage-Backend": str(file_record.get("storage_backend") or "database"),
            },
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to download saved BOM file from database.")
        raise HTTPException(status_code=500, detail="Failed to download saved BOM file from database.")


@app.get("/api/search")
async def search_drawings(category: str, component: str):
    """Search SharePoint files by category + component across configured target folders."""
    import base64
    import httpx
    import msal
    import urllib.parse
    
    tenant_id = os.getenv("SHAREPOINT_TENANT_ID")
    client_id = os.getenv("SHAREPOINT_CLIENT_ID")
    client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
    target_url_raw = os.getenv("SHAREPOINT_TARGET_URL", "")

    if not all([tenant_id, client_id, client_secret]):
        logger.error("SharePoint AD credentials are not fully configured in .env")
        raise HTTPException(status_code=500, detail="SharePoint credentials are not fully configured.")

    target_urls = [u.strip() for u in str(target_url_raw).split(",") if u.strip()]
    if not target_urls:
        logger.error("SHAREPOINT_TARGET_URL is empty in .env")
        raise HTTPException(status_code=500, detail="No SharePoint target URL configured.")

    normalized_category = str(category or "").strip()
    normalized_component = str(component or "").strip()
    if len(normalized_component) < 2:
        return {
            "status": "success",
            "search_scopes": [],
            "results": [],
        }

    def _extract_site_name(target_url: str) -> str:
        parsed = urllib.parse.urlparse(target_url)
        segments = [seg for seg in parsed.path.split("/") if seg]
        lowered = [seg.lower() for seg in segments]
        if "sites" in lowered:
            idx = lowered.index("sites")
            if idx + 1 < len(segments):
                return urllib.parse.unquote(segments[idx + 1])
        return parsed.netloc.split(".")[0] or "SharePoint"

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app_msal = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret,
    )
    token = app_msal.acquire_token_silent(["https://graph.microsoft.com/.default"], account=None)
    if not token:
        token = await asyncio.to_thread(
            app_msal.acquire_token_for_client,
            scopes=["https://graph.microsoft.com/.default"],
        )
    if "access_token" not in token:
        logger.error("Failed to acquire Graph access token: %s", token)
        raise HTTPException(status_code=500, detail="Failed to acquire Azure AD access token.")

    headers = {"Authorization": f"Bearer {token['access_token']}"}
    drawings_by_key: dict[str, dict[str, Any]] = {}
    scope_map: dict[str, dict[str, str]] = {}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for target_url in target_urls:
                try:
                    encoded = base64.urlsafe_b64encode(target_url.encode("utf-8")).decode("utf-8").rstrip("=")
                    share_id = f"u!{encoded}"
                    resolved = await client.get(
                        f"https://graph.microsoft.com/v1.0/shares/{share_id}/driveItem",
                        headers=headers,
                    )
                    if resolved.status_code != 200:
                        logger.warning("Cannot resolve SharePoint URL %s: %s", target_url, resolved.text)
                        continue

                    resolved_item = resolved.json()
                    drive_id = str(resolved_item.get("parentReference", {}).get("driveId") or "").strip()
                    folder_id = str(resolved_item.get("id") or "").strip()
                    root_name = str(resolved_item.get("name") or "Folder").strip()
                    site_name = _extract_site_name(target_url)
                    if not drive_id or not folder_id:
                        continue

                    children_res = await client.get(
                        f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}/children",
                        headers=headers,
                    )
                    category_map: dict[str, str] = {}
                    if children_res.status_code == 200:
                        children = children_res.json().get("value", [])
                        for child in children:
                            if "folder" in child:
                                name = str(child.get("name") or "").strip()
                                if name and child.get("id"):
                                    category_map[name.lower()] = str(child["id"])

                    target_folder_id = category_map.get(normalized_category.lower(), folder_id)
                    scope_key = f"{site_name}|{root_name}|{normalized_category}"
                    scope_map[scope_key] = {
                        "site": site_name,
                        "root": root_name,
                        "category": normalized_category,
                    }

                    component_lc = normalized_component.lower()

                    def _append_matched_file(item: dict[str, Any]) -> None:
                        file_name = str(item.get("name") or "").strip()
                        if not file_name:
                            return
                        if component_lc not in file_name.lower():
                            return

                        item_id = str(item.get("id") or "").strip()
                        if not item_id:
                            return

                        ext = Path(file_name).suffix.lower().lstrip(".")
                        file_type = (ext.upper() if ext else "FILE")[:8]
                        key = f"{drive_id}:{item_id}:{normalized_component}"
                        drawings_by_key[key] = {
                            "id": key,
                            "item_id": item_id,
                            "drive_id": drive_id,
                            "name": file_name,
                            "version": "Live",
                            "type": file_type,
                            "date": str(item.get("lastModifiedDateTime") or "")[:10] or "Unknown",
                            "source_site": site_name,
                            "source_root": root_name,
                            "source_category": normalized_category,
                            "web_url": str(item.get("webUrl") or ""),
                        }

                    # Pass 1: Graph index-based search (fast, but may miss some binary formats)
                    query = urllib.parse.quote(normalized_component)
                    search_res = await client.get(
                        f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{target_folder_id}/search(q='{query}')",
                        headers=headers,
                    )
                    if search_res.status_code == 200:
                        for item in search_res.json().get("value", []):
                            if "folder" in item:
                                continue
                            _append_matched_file(item)
                    else:
                        logger.warning("Graph search failed for scope %s: %s", scope_key, search_res.text)

                    # Pass 2: Folder traversal fallback to include all file formats by filename match.
                    pending_folders = [target_folder_id]
                    visited_folders: set[str] = set()
                    max_folder_scan = 1200
                    scanned_count = 0

                    while pending_folders and scanned_count < max_folder_scan:
                        current_folder = pending_folders.pop(0)
                        if not current_folder or current_folder in visited_folders:
                            continue

                        visited_folders.add(current_folder)
                        scanned_count += 1

                        next_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{current_folder}/children?$top=200"
                        while next_url:
                            children_page = await client.get(next_url, headers=headers)
                            if children_page.status_code != 200:
                                logger.warning(
                                    "Graph children listing failed for scope %s folder %s: %s",
                                    scope_key,
                                    current_folder,
                                    children_page.text,
                                )
                                break

                            page_payload = children_page.json()
                            for child in page_payload.get("value", []):
                                if "folder" in child:
                                    child_folder_id = str(child.get("id") or "").strip()
                                    if child_folder_id and child_folder_id not in visited_folders:
                                        pending_folders.append(child_folder_id)
                                    continue
                                _append_matched_file(child)

                            next_url = page_payload.get("@odata.nextLink")

                    if scanned_count >= max_folder_scan:
                        logger.warning(
                            "Folder traversal stopped at cap (%s) for scope %s",
                            max_folder_scan,
                            scope_key,
                        )
                except Exception:
                    logger.exception("Unexpected error while searching target URL: %s", target_url)

        return {
            "status": "success",
            "search_scopes": list(scope_map.values()),
            "results": list(drawings_by_key.values()),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("SharePoint search implementation error")
        raise HTTPException(status_code=500, detail="SharePoint search failed.")


@app.get("/api/sp_file")
async def serve_sharepoint_file(
    drive_id: str,
    item_id: str,
    filename: str = Query(default="file"),
    mode: str = Query(default="preview", pattern="^(preview|download)$"),
):
    """Serve SharePoint file content through backend for stable preview/download behavior."""
    import httpx
    import msal

    tenant_id = os.getenv("SHAREPOINT_TENANT_ID")
    client_id = os.getenv("SHAREPOINT_CLIENT_ID")
    client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
    if not all([tenant_id, client_id, client_secret]):
        raise HTTPException(status_code=500, detail="SharePoint credentials are not fully configured.")

    safe_drive = str(drive_id or "").strip()
    safe_item = str(item_id or "").strip()
    if not safe_drive or not safe_item:
        raise HTTPException(status_code=400, detail="drive_id and item_id are required.")

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app_msal = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret,
    )
    token = app_msal.acquire_token_silent(["https://graph.microsoft.com/.default"], account=None)
    if not token:
        token = await asyncio.to_thread(
            app_msal.acquire_token_for_client,
            scopes=["https://graph.microsoft.com/.default"],
        )
    if "access_token" not in token:
        raise HTTPException(status_code=500, detail="Failed to acquire Azure AD access token.")

    headers = {"Authorization": f"Bearer {token['access_token']}"}
    content_url = f"https://graph.microsoft.com/v1.0/drives/{safe_drive}/items/{safe_item}/content"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            file_res = await client.get(content_url, headers=headers)

        if file_res.status_code != 200:
            logger.error("Failed to fetch SharePoint file content: %s", file_res.text)
            raise HTTPException(status_code=502, detail="Failed to fetch file from SharePoint.")

        safe_name = _safe_filename(filename)
        content_type = file_res.headers.get("Content-Type") or _guess_mime_type(safe_name)
        disposition = "attachment" if mode == "download" else "inline"

        return Response(
            content=file_res.content,
            media_type=content_type,
            headers={"Content-Disposition": f'{disposition}; filename="{safe_name}"'},
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("SharePoint file proxy failed")
        raise HTTPException(status_code=500, detail="Failed to stream SharePoint file.")

if __name__ == "__main__":
    uvicorn.run("BOM_Backend_API:app", host="0.0.0.0", port=8000, reload=True)
