from __future__ import annotations

import asyncio
import base64
import logging
import os
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
import msal
from fastapi import HTTPException
from fastapi.responses import Response

from app.services.bom_utils import guess_mime_type, safe_filename

logger = logging.getLogger("bom_api")


def _extract_site_name(target_url: str) -> str:
    parsed = urllib.parse.urlparse(target_url)
    segments = [seg for seg in parsed.path.split("/") if seg]
    lowered = [seg.lower() for seg in segments]
    if "sites" in lowered:
        idx = lowered.index("sites")
        if idx + 1 < len(segments):
            return urllib.parse.unquote(segments[idx + 1])
    return parsed.netloc.split(".")[0] or "SharePoint"


def _get_graph_access_token() -> str:
    tenant_id = os.getenv("SHAREPOINT_TENANT_ID")
    client_id = os.getenv("SHAREPOINT_CLIENT_ID")
    client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")

    if not all([tenant_id, client_id, client_secret]):
        logger.error("SharePoint AD credentials are not fully configured in .env")
        raise HTTPException(status_code=500, detail="SharePoint credentials are not fully configured.")

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app_msal = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret,
    )

    token = app_msal.acquire_token_silent(["https://graph.microsoft.com/.default"], account=None)
    if not token:
        token = app_msal.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

    access_token = token.get("access_token") if isinstance(token, dict) else None
    if not access_token:
        logger.error("Failed to acquire Graph access token: %s", token)
        raise HTTPException(status_code=500, detail="Failed to acquire Azure AD access token.")

    return access_token


async def search_drawings(category: str, component: str) -> dict[str, Any]:
    """Search SharePoint files by category + component across configured target folders."""
    target_url_raw = os.getenv("SHAREPOINT_TARGET_URL", "")
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

    access_token = await asyncio.to_thread(_get_graph_access_token)
    headers = {"Authorization": f"Bearer {access_token}"}

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

                    def append_matched_file(item: dict[str, Any]) -> None:
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

                    query = urllib.parse.quote(normalized_component)
                    search_res = await client.get(
                        f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{target_folder_id}/search(q='{query}')",
                        headers=headers,
                    )
                    if search_res.status_code == 200:
                        for item in search_res.json().get("value", []):
                            if "folder" in item:
                                continue
                            append_matched_file(item)
                    else:
                        logger.warning("Graph search failed for scope %s: %s", scope_key, search_res.text)

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
                                append_matched_file(child)

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

    access_token = await asyncio.to_thread(_get_graph_access_token)
    headers = {"Authorization": f"Bearer {access_token}"}
    content_url = f"https://graph.microsoft.com/v1.0/drives/{safe_drive}/items/{safe_item}/content"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            file_res = await client.get(content_url, headers=headers)

        if file_res.status_code != 200:
            logger.error("Failed to fetch SharePoint file content: %s", file_res.text)
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
