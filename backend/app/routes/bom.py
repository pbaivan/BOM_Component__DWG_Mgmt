from __future__ import annotations

from fastapi import APIRouter

from app.routes.bom_ingest import router as bom_ingest_router
from app.routes.bom_records import router as bom_records_router

router = APIRouter()
router.include_router(bom_ingest_router)
router.include_router(bom_records_router)
