from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.services.bom_models import MetadataSaveRequest
from app.services.bom_records_service import (
    create_new_save_record as svc_create_new_save_record,
    delete_save_record as svc_delete_save_record,
    get_saved_bom_table as svc_get_saved_bom_table,
    list_save_records as svc_list_save_records,
    read_saved_file_from_database as svc_read_saved_file_from_database,
    save_file_and_metadata_record as svc_save_file_and_metadata_record,
    save_file_record as svc_save_file_record,
    save_metadata_record as svc_save_metadata_record,
)
from app.services.bom_utils import safe_filename

logger = logging.getLogger("bom_api")
router = APIRouter()


@router.post("/save/new-record")
async def create_save_record():
    try:
        result = await asyncio.to_thread(svc_create_new_save_record)
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


@router.post("/save/file")
async def save_bom_file(record_id: str = Form(...), file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    contents = await file.read()

    try:
        result = await asyncio.to_thread(svc_save_file_record, record_id, file.filename, contents, file.content_type)
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


@router.post("/save/metadata")
async def save_bom_metadata(payload: MetadataSaveRequest):
    try:
        result = await asyncio.to_thread(
            svc_save_metadata_record,
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


@router.post("/save/both")
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
            svc_save_file_and_metadata_record,
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


@router.delete("/save/record/{record_id}")
async def delete_save_record(record_id: str):
    try:
        await asyncio.to_thread(svc_delete_save_record, record_id)
        return {
            "status": "success",
            "message": "BOM record and all associated tables have been permanently deleted.",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete the BOM record.")
        raise HTTPException(status_code=500, detail="Failed to delete the BOM record.")


@router.get("/save/list")
async def list_save_records(limit: int = Query(default=50, ge=1, le=200)):
    try:
        records = await asyncio.to_thread(svc_list_save_records, limit)
        return {
            "status": "success",
            "records": records,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to list save records.")
        raise HTTPException(status_code=500, detail="Failed to list save records.")


@router.get("/save/table/{record_id}")
async def get_saved_bom_table(record_id: str, offset: int = Query(default=0, ge=0), limit: int = Query(default=100000, ge=1)):
    try:
        result = await asyncio.to_thread(svc_get_saved_bom_table, record_id, offset, limit)
        return {
            "status": "success",
            **result,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch saved BOM table data.")
        raise HTTPException(status_code=500, detail="Failed to fetch saved BOM table data.")


@router.get("/save/file/{record_id}/download")
async def download_saved_bom_file(record_id: str):
    try:
        file_record = await asyncio.to_thread(svc_read_saved_file_from_database, record_id)
        safe_file_name = safe_filename(file_record["file_name"])
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
