from __future__ import annotations

from fastapi import APIRouter

from app.routes.bom import router as bom_router
from app.routes.health import router as health_router
from app.routes.sharepoint import router as sharepoint_router

router = APIRouter()
router.include_router(health_router)
router.include_router(bom_router)
router.include_router(sharepoint_router)
