from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from fastapi import HTTPException


def normalize_text(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"{field_name} is required.")
    return normalized


def normalize_record_id(record_id: str) -> str:
    try:
        return str(uuid.UUID(str(record_id).strip()))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid record_id.")


def safe_filename(filename: str) -> str:
    safe_name = Path(str(filename or "")).name.strip()
    if not safe_name:
        return "source.xlsx"
    return safe_name.replace("/", "_").replace("\\", "_")


def status_from_flags(file_saved: bool, metadata_saved: bool) -> str:
    if file_saved and metadata_saved:
        return "paired"
    if file_saved:
        return "file_saved"
    if metadata_saved:
        return "metadata_saved"
    return "draft"


def guess_mime_type(file_name: str, fallback: str | None = None) -> str:
    guessed, _ = mimetypes.guess_type(str(file_name or ""))
    return guessed or fallback or "application/octet-stream"
