from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import LOCAL_ORIGIN_REGEX, get_allowed_origins
from app.db import close_db_pool, init_db_pool
from app.routes.api import router as api_router
from app.services import bom_records_service

logger = logging.getLogger("bom_api")

app = FastAPI(title="BOM Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_origin_regex=LOCAL_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    try:
        await asyncio.to_thread(init_db_pool)
        await asyncio.to_thread(bom_records_service.init_persistence_layer)
        logger.info("Persistence layer initialized and ready.")
    except Exception:
        logger.exception("Failed to initialize persistence layer.")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    try:
        await asyncio.to_thread(close_db_pool)
    except Exception:
        logger.exception("Failed while closing database resources.")


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": str(exc.detail)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, __: Exception):
    logger.exception("Unhandled server exception.")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error."},
    )


@app.get("/")
async def root():
    return {
        "message": "Success! BOM Backend is running.",
        "docs_url": "Visit /docs for API documentation",
    }


app.include_router(api_router, prefix="/api")
