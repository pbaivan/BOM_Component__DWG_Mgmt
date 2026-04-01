from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pandas as pd
import io
import uvicorn
import asyncio
import logging
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
    """Parse BOM content in a worker thread to avoid blocking the event loop."""
    stream = io.BytesIO(contents)

    if extension == ".csv":
        df = pd.read_csv(stream, keep_default_na=False, na_filter=False)
    else:
        df = pd.read_excel(
            stream,
            engine="openpyxl",
            keep_default_na=False,
            na_filter=False,
        )

    columns = [str(col) for col in df.columns.tolist()]
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
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bom_save_records (
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
                    record_id UUID PRIMARY KEY REFERENCES bom_save_records(record_id) ON DELETE CASCADE,
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
                CREATE TABLE IF NOT EXISTS bom_saved_metadata (
                    record_id UUID PRIMARY KEY REFERENCES bom_save_records(record_id) ON DELETE CASCADE,
                    file_name TEXT NOT NULL,
                    upload_date TEXT NOT NULL,
                    version TEXT NOT NULL,
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
        FROM bom_save_records
        WHERE record_id = %s
        FOR UPDATE;
        """,
        (record_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="record_id not found.")
    return row


def _create_new_save_record() -> dict[str, Any]:
    record_id = str(uuid.uuid4())
    with _get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bom_save_records (record_id, status, file_saved, metadata_saved)
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


def _save_file_record(record_id: str, file_name: str, contents: bytes) -> dict[str, Any]:
    normalized_record_id = _normalize_record_id(record_id)
    original_file_name = _safe_filename(file_name)
    extension = Path(original_file_name).suffix.lower()

    if extension not in ALLOWED_SAVE_FILE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .xlsx and .csv files can be stored.")
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File is too large. Max allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")

    record_dir = FILE_STORAGE_DIR / normalized_record_id
    record_dir.mkdir(parents=True, exist_ok=True)
    stored_file_name = f"source{extension}"
    stored_path = record_dir / stored_file_name
    stored_path.write_bytes(contents)
    file_sha256 = hashlib.sha256(contents).hexdigest()

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
                    file_sha256
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (record_id)
                DO UPDATE SET
                    original_file_name = EXCLUDED.original_file_name,
                    stored_file_name = EXCLUDED.stored_file_name,
                    stored_path = EXCLUDED.stored_path,
                    file_size = EXCLUDED.file_size,
                    file_sha256 = EXCLUDED.file_sha256,
                    updated_at = NOW();
                """,
                (
                    normalized_record_id,
                    original_file_name,
                    stored_file_name,
                    str(stored_path),
                    len(contents),
                    file_sha256,
                ),
            )

            cur.execute(
                """
                UPDATE bom_save_records
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
                UPDATE bom_save_records
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

    record_dir = FILE_STORAGE_DIR / normalized_record_id
    record_dir.mkdir(parents=True, exist_ok=True)
    stored_file_name = f"source{extension}"
    stored_path = record_dir / stored_file_name
    stored_path.write_bytes(contents)
    file_sha256 = hashlib.sha256(contents).hexdigest()

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
                    file_sha256
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (record_id)
                DO UPDATE SET
                    original_file_name = EXCLUDED.original_file_name,
                    stored_file_name = EXCLUDED.stored_file_name,
                    stored_path = EXCLUDED.stored_path,
                    file_size = EXCLUDED.file_size,
                    file_sha256 = EXCLUDED.file_sha256,
                    updated_at = NOW();
                """,
                (
                    normalized_record_id,
                    original_file_name,
                    stored_file_name,
                    str(stored_path),
                    len(contents),
                    file_sha256,
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
                UPDATE bom_save_records
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
                    f.saved_at AS file_saved_at,
                    m.saved_at AS metadata_saved_at
                FROM bom_save_records r
                LEFT JOIN bom_saved_metadata m ON m.record_id = r.record_id
                LEFT JOIN bom_saved_files f ON f.record_id = r.record_id
                ORDER BY r.updated_at DESC
                LIMIT %s;
                """,
                (limit,),
            )
            return cur.fetchall()


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
async def upload_bom(file: UploadFile = File(...)):
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

        return {
            "status": "success",
            "rows": len(rows),
            "columns": columns,
            "data": rows
        }
    except HTTPException:
        raise
    except (ValueError, pd.errors.ParserError, UnicodeDecodeError):
        logger.warning("Upload rejected due to invalid file format: %s", file.filename)
        raise HTTPException(status_code=400, detail="Invalid or corrupted BOM file format.")
    except Exception:
        logger.exception("Unexpected error while processing upload.")
        raise HTTPException(status_code=500, detail="Failed to process BOM file.")


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
        result = await asyncio.to_thread(_save_file_record, record_id, file.filename, contents)
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


@app.get("/api/search")
async def search_drawings(category: str, component: str):
    """
    Mock API simulating the SharePoint Graph API search behavior.
    """
    # Simulate network delay for realistic UI loading experience
    await asyncio.sleep(0.6)

    mock_drawings = []

    # Generate mock drawing data based on the requested component number
    if component and "-" in component:
        mock_drawings = [
            {
                "id": f"doc_{component}_1",
                "name": f"{component}_Assembly_Drawing.pdf",
                "version": "A01",
                "type": "PDF",
                "date": "2023-10-15"
            },
            {
                "id": f"doc_{component}_2",
                "name": f"{component}_Part_Details.pdf",
                "version": "B02",
                "type": "PDF",
                "date": "2023-11-20"
            },
            {
                "id": f"doc_{component}_3",
                "name": f"{component}_3D_Model.step",
                "version": "Release",
                "type": "CAD",
                "date": "2023-12-01"
            }
        ]
    elif component:
        mock_drawings = [
            {
                "id": f"doc_{component}_4",
                "name": f"{component}_Datasheet.pdf",
                "version": "1.0",
                "type": "PDF",
                "date": "2024-01-10"
            }
        ]

    # Generate a structured array for the SharePoint Breadcrumb path
    sharepoint_path_array = [
        "SharePoint Root",
        "Engineering Documents",
        category if category else "Uncategorized",
        component if component else "Unknown Model",
        "Released Drawings"
    ]

    return {
        "status": "success",
        "mock_category_folder": category,
        "sharepoint_path": sharepoint_path_array,
        "results": mock_drawings
    }


if __name__ == "__main__":
    uvicorn.run("BOM_Backend_API:app", host="0.0.0.0", port=8000, reload=True)