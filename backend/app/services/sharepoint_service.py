from __future__ import annotations

"""Compatibility facade for split SharePoint service modules."""

from app.services.sharepoint_file_proxy import serve_sharepoint_file
from app.services.sharepoint_search import search_drawings

__all__ = ["search_drawings", "serve_sharepoint_file"]
