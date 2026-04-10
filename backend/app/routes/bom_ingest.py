from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES
from app.services.bom_parser import parse_bom_rows
from app.services.bom_records_service import save_file_record, save_uploaded_bom_table

logger = logging.getLogger("bom_api")
router = APIRouter()


@router.post("/upload")
async def upload_bom(file: UploadFile = File(...), record_id: str | None = Form(default=None)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .csv and .xlsx files are supported.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Max allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    try:
        columns, rows = await asyncio.to_thread(parse_bom_rows, contents, extension)
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
            save_uploaded_bom_table,
            file.filename,
            extension,
            columns,
            rows,
            record_id,
        )
        file_result = await asyncio.to_thread(
            save_file_record,
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
