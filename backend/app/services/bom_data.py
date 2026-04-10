from __future__ import annotations

"""Compatibility facade for BOM data services.

Active code should import from dedicated modules:
- app.services.bom_models
- app.services.bom_parser
- app.services.bom_utils
- app.services.bom_records_service

This facade is kept to avoid breaking legacy imports during migration.
"""

from app.services.bom_models import MetadataSaveRequest
from app.services.bom_parser import parse_bom_rows
from app.services.bom_records_service import (
    create_new_save_record,
    delete_save_record,
    get_saved_bom_table,
    init_persistence_layer,
    list_save_records,
    read_saved_file_from_database,
    save_file_and_metadata_record,
    save_file_record,
    save_metadata_record,
    save_uploaded_bom_table,
)
from app.services.bom_utils import (
    guess_mime_type,
    normalize_record_id,
    normalize_text,
    safe_filename,
    status_from_flags,
)

__all__ = [
    "MetadataSaveRequest",
    "parse_bom_rows",
    "normalize_text",
    "normalize_record_id",
    "safe_filename",
    "status_from_flags",
    "guess_mime_type",
    "init_persistence_layer",
    "save_uploaded_bom_table",
    "create_new_save_record",
    "save_file_record",
    "save_metadata_record",
    "save_file_and_metadata_record",
    "delete_save_record",
    "list_save_records",
    "read_saved_file_from_database",
    "get_saved_bom_table",
]
