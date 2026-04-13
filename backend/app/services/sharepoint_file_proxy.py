from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import HTTPException
from fastapi.responses import Response

from app.services.bom_utils import guess_mime_type, safe_filename
from app.services.sharepoint_auth import get_graph_access_token

logger = logging.getLogger("bom_api")


async def serve_sharepoint_file(
    drive_id: str,
    item_id: str,
    filename: str = "file",
    mode: str = "preview",
) -> Response:
    """Serve SharePoint file content through backend for stable preview/download behavior."""
    safe_drive = str(drive_id or "").strip()
    safe_item = str(item_id or "").strip()
    if not safe_drive or not safe_item:
        raise HTTPException(status_code=400, detail="drive_id and item_id are required.")

    access_token = await asyncio.to_thread(get_graph_access_token)
    headers = {"Authorization": f"Bearer {access_token}"}
    content_url = f"https://graph.microsoft.com/v1.0/drives/{safe_drive}/items/{safe_item}/content"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            file_res = await client.get(content_url, headers=headers)

        if file_res.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch file from SharePoint.")

        safe_name = safe_filename(filename)
        content_type = file_res.headers.get("Content-Type") or guess_mime_type(safe_name)
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
