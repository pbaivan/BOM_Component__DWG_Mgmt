from __future__ import annotations

from pydantic import BaseModel


class MetadataSaveRequest(BaseModel):
    record_id: str
    file_name: str
    upload_date: str
    version: str
