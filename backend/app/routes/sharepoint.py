from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import sharepoint_service

router = APIRouter()


@router.get("/search")
async def search_drawings(
    category: str,
    component: str,
    include_debug: bool = Query(default=False),
):
    return await sharepoint_service.search_drawings(
        category,
        component,
        include_debug=include_debug,
    )


@router.get("/sp_file")
async def serve_sharepoint_file(
    drive_id: str,
    item_id: str,
    filename: str = Query(default="file"),
    mode: str = Query(default="preview", pattern="^(preview|download)$"),
):
    return await sharepoint_service.serve_sharepoint_file(
        drive_id=drive_id,
        item_id=item_id,
        filename=filename,
        mode=mode,
    )
