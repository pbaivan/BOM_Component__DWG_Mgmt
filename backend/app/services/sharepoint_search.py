from __future__ import annotations

import asyncio
import logging
import os
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException

from app.services.sharepoint_auth import get_graph_access_token
from app.services.sharepoint_utils import encode_share_id, extract_site_name, get_target_urls

logger = logging.getLogger("bom_api")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid %s value '%s'. Falling back to %s.", name, raw, default)
        return default


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(minimum, int(raw))
    except (TypeError, ValueError):
        logger.warning("Invalid %s value '%s'. Falling back to %s.", name, raw, default)
        return default


_SEARCH_TIMEOUT_SECONDS = _env_float("SHAREPOINT_SEARCH_TIMEOUT_SECONDS", 30.0)
_TARGET_CONCURRENCY = _env_int("SHAREPOINT_TARGET_CONCURRENCY", 4)
_MAX_FOLDER_SCAN = _env_int("SHAREPOINT_MAX_FOLDER_SCAN", 1200)


def _append_matched_file(
    item: dict[str, Any],
    *,
    component_lc: str,
    normalized_component: str,
    normalized_category: str,
    drive_id: str,
    site_name: str,
    root_name: str,
    drawings_by_key: dict[str, dict[str, Any]],
) -> None:
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


async def _search_single_target(
    client: httpx.AsyncClient,
    *,
    target_url: str,
    headers: dict[str, str],
    normalized_category: str,
    normalized_component: str,
) -> dict[str, Any]:
    drawings_by_key: dict[str, dict[str, Any]] = {}
    started_at = time.perf_counter()
    diagnostic: dict[str, Any] = {
        "target_url": target_url,
        "status": "unknown",
        "site": "",
        "root": "",
        "category": normalized_category,
        "resolved_status": None,
        "children_status": None,
        "search_status": None,
        "scanned_folders": 0,
        "matched_files": 0,
        "error": "",
        "elapsed_ms": 0.0,
    }

    try:
        share_id = encode_share_id(target_url)
        resolved = await client.get(
            f"https://graph.microsoft.com/v1.0/shares/{share_id}/driveItem",
            headers=headers,
        )
        diagnostic["resolved_status"] = resolved.status_code
        if resolved.status_code != 200:
            logger.warning("Cannot resolve SharePoint URL %s: %s", target_url, resolved.text)
            diagnostic["status"] = "resolve_failed"
            diagnostic["error"] = f"resolve_status_{resolved.status_code}"
            return {"drawings_by_key": drawings_by_key, "scope": None, "diagnostic": diagnostic}

        resolved_item = resolved.json()
        drive_id = str(resolved_item.get("parentReference", {}).get("driveId") or "").strip()
        folder_id = str(resolved_item.get("id") or "").strip()
        root_name = str(resolved_item.get("name") or "Folder").strip()
        site_name = extract_site_name(target_url)
        diagnostic["site"] = site_name
        diagnostic["root"] = root_name
        if not drive_id or not folder_id:
            diagnostic["status"] = "resolved_missing_ids"
            diagnostic["error"] = "missing_drive_or_folder_id"
            return {"drawings_by_key": drawings_by_key, "scope": None, "diagnostic": diagnostic}

        children_res = await client.get(
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}/children",
            headers=headers,
        )
        diagnostic["children_status"] = children_res.status_code
        category_map: dict[str, str] = {}
        if children_res.status_code == 200:
            children = children_res.json().get("value", [])
            for child in children:
                if "folder" in child:
                    name = str(child.get("name") or "").strip()
                    if name and child.get("id"):
                        category_map[name.lower()] = str(child["id"])

        target_folder_id = category_map.get(normalized_category.lower(), folder_id)
        scope = {
            "site": site_name,
            "root": root_name,
            "category": normalized_category,
        }

        component_lc = normalized_component.lower()

        query = urllib.parse.quote(normalized_component)
        search_res = await client.get(
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{target_folder_id}/search(q='{query}')",
            headers=headers,
        )
        diagnostic["search_status"] = search_res.status_code
        if search_res.status_code == 200:
            for item in search_res.json().get("value", []):
                if "folder" in item:
                    continue
                _append_matched_file(
                    item,
                    component_lc=component_lc,
                    normalized_component=normalized_component,
                    normalized_category=normalized_category,
                    drive_id=drive_id,
                    site_name=site_name,
                    root_name=root_name,
                    drawings_by_key=drawings_by_key,
                )
        else:
            logger.warning("Graph search failed for scope %s|%s|%s: %s", site_name, root_name, normalized_category, search_res.text)

        pending_folders = [target_folder_id]
        visited_folders: set[str] = set()
        scanned_count = 0

        while pending_folders and scanned_count < _MAX_FOLDER_SCAN:
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
                        "Graph children listing failed for scope %s|%s|%s folder %s: %s",
                        site_name,
                        root_name,
                        normalized_category,
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
                    _append_matched_file(
                        child,
                        component_lc=component_lc,
                        normalized_component=normalized_component,
                        normalized_category=normalized_category,
                        drive_id=drive_id,
                        site_name=site_name,
                        root_name=root_name,
                        drawings_by_key=drawings_by_key,
                    )

                next_url = page_payload.get("@odata.nextLink")

        if scanned_count >= _MAX_FOLDER_SCAN:
            logger.warning(
                "Folder traversal stopped at cap (%s) for scope %s|%s|%s",
                _MAX_FOLDER_SCAN,
                site_name,
                root_name,
                normalized_category,
            )

        diagnostic["scanned_folders"] = scanned_count
        diagnostic["matched_files"] = len(drawings_by_key)
        diagnostic["status"] = "ok"
        return {"drawings_by_key": drawings_by_key, "scope": scope, "diagnostic": diagnostic}
    except Exception as exc:
        logger.exception("Unexpected error while searching target URL: %s", target_url)
        diagnostic["status"] = "exception"
        diagnostic["error"] = f"{type(exc).__name__}: {exc}"
        diagnostic["matched_files"] = len(drawings_by_key)
        return {"drawings_by_key": drawings_by_key, "scope": None, "diagnostic": diagnostic}
    finally:
        diagnostic["elapsed_ms"] = round((time.perf_counter() - started_at) * 1000.0, 2)


async def _search_target_with_limit(
    semaphore: asyncio.Semaphore,
    client: httpx.AsyncClient,
    *,
    target_url: str,
    headers: dict[str, str],
    normalized_category: str,
    normalized_component: str,
) -> dict[str, Any]:
    async with semaphore:
        return await _search_single_target(
            client,
            target_url=target_url,
            headers=headers,
            normalized_category=normalized_category,
            normalized_component=normalized_component,
        )


async def search_drawings(category: str, component: str, include_debug: bool = False) -> dict[str, Any]:
    """Search SharePoint files by category + component across configured target folders."""
    target_urls = get_target_urls()
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

    access_token = await asyncio.to_thread(get_graph_access_token)
    headers = {"Authorization": f"Bearer {access_token}"}

    drawings_by_key: dict[str, dict[str, Any]] = {}
    scope_map: dict[str, dict[str, str]] = {}
    diagnostics: list[dict[str, Any]] = []
    started_at = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT_SECONDS) as client:
            semaphore = asyncio.Semaphore(_TARGET_CONCURRENCY)
            tasks = [
                _search_target_with_limit(
                    semaphore,
                    client,
                    target_url=target_url,
                    headers=headers,
                    normalized_category=normalized_category,
                    normalized_component=normalized_component,
                )
                for target_url in target_urls
            ]

            per_target = await asyncio.gather(*tasks)
            for item in per_target:
                drawings_by_key.update(item.get("drawings_by_key") or {})
                scope = item.get("scope")
                if scope:
                    scope_key = f"{scope['site']}|{scope['root']}|{scope['category']}"
                    scope_map[scope_key] = scope
                diagnostic = item.get("diagnostic")
                if isinstance(diagnostic, dict):
                    diagnostics.append(diagnostic)

        elapsed_ms = round((time.perf_counter() - started_at) * 1000.0, 2)
        success_targets = sum(1 for item in diagnostics if item.get("status") == "ok")
        failed_targets = max(0, len(diagnostics) - success_targets)

        logger.info(
            "SharePoint search summary category=%s component=%s targets=%s success=%s failed=%s results=%s elapsed_ms=%s concurrency=%s",
            normalized_category,
            normalized_component,
            len(target_urls),
            success_targets,
            failed_targets,
            len(drawings_by_key),
            elapsed_ms,
            _TARGET_CONCURRENCY,
        )

        payload: dict[str, Any] = {
            "status": "success",
            "search_scopes": list(scope_map.values()),
            "results": list(drawings_by_key.values()),
        }
        if include_debug:
            payload["debug"] = {
                "elapsed_ms": elapsed_ms,
                "target_count": len(target_urls),
                "target_concurrency": _TARGET_CONCURRENCY,
                "success_targets": success_targets,
                "failed_targets": failed_targets,
                "targets": diagnostics,
            }

        return payload
    except HTTPException:
        raise
    except Exception:
        logger.exception("SharePoint search implementation error")
        raise HTTPException(status_code=500, detail="SharePoint search failed.")
