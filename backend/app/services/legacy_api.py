from __future__ import annotations

"""Compatibility exports for legacy imports.

This module is retained so older import paths keep working while all logic
now lives in dedicated service modules.
"""

from app.services import bom_data, sharepoint_service

MetadataSaveRequest = bom_data.MetadataSaveRequest

parse_bom_rows = bom_data.parse_bom_rows
safe_filename = bom_data.safe_filename
init_persistence_layer = bom_data.init_persistence_layer
create_new_save_record = bom_data.create_new_save_record
save_uploaded_bom_table = bom_data.save_uploaded_bom_table
save_file_record = bom_data.save_file_record
save_metadata_record = bom_data.save_metadata_record
save_file_and_metadata_record = bom_data.save_file_and_metadata_record
delete_save_record = bom_data.delete_save_record
list_save_records = bom_data.list_save_records
read_saved_file_from_database = bom_data.read_saved_file_from_database
get_saved_bom_table = bom_data.get_saved_bom_table
search_drawings = sharepoint_service.search_drawings
serve_sharepoint_file = sharepoint_service.serve_sharepoint_file
