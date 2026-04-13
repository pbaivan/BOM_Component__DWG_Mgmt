from __future__ import annotations

import asyncio
import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import LOCAL_ORIGIN_REGEX, get_allowed_origins
from app.db import close_db_pool, init_db_pool
from app.observability import (
    configure_logging,
    generate_request_id,
    get_request_id,
    reset_request_id,
    set_request_id,
)
from app.routes.api import router as api_router
from app.services import bom_records_service

configure_logging()
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


@app.middleware("http")
async def request_observability_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or generate_request_id()
    token = set_request_id(request_id)
    started_at = time.perf_counter()
    response = None

    try:
        response = await call_next(request)
        return response
    finally:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000.0, 2)
        status_code = response.status_code if response is not None else 500
        client_ip = request.client.host if request.client else ""

        logger.info(
            "Request completed",
            extra={
                "event": "http.request",
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "elapsed_ms": elapsed_ms,
                "client_ip": client_ip,
            },
        )

        if response is not None:
            response.headers["X-Request-ID"] = request_id

        reset_request_id(token)


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
        content={
            "status": "error",
            "message": str(exc.detail),
            "request_id": get_request_id(),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    logger.warning(
        "Request validation failed",
        extra={
            "event": "http.validation_error",
            "errors": exc.errors(),
        },
    )
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Request validation error.",
            "errors": exc.errors(),
            "request_id": get_request_id(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, __: Exception):
    logger.exception("Unhandled server exception.")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error.",
            "request_id": get_request_id(),
        },
    )


@app.get("/")
async def root():
    return {
        "message": "Success! BOM Backend is running.",
        "docs_url": "Visit /docs for API documentation",
    }


app.include_router(api_router, prefix="/api")
