from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import msal
from fastapi import HTTPException

logger = logging.getLogger("bom_api")


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(minimum, int(raw))
    except (TypeError, ValueError):
        logger.warning("Invalid %s value '%s'. Falling back to %s.", name, raw, default)
        return default


_TOKEN_MIN_TTL_SECONDS = _env_int("SHAREPOINT_TOKEN_MIN_TTL_SECONDS", 120, minimum=30)
_TOKEN_LOCK = threading.Lock()
_TOKEN_CACHE = {
    "access_token": "",
    "expires_at": 0.0,
}


def _read_cached_token() -> str | None:
    token = str(_TOKEN_CACHE.get("access_token") or "")
    expires_at = float(_TOKEN_CACHE.get("expires_at") or 0.0)
    if token and time.time() < expires_at:
        return token
    return None


def _write_cached_token(token_payload: dict[str, Any]) -> str:
    access_token = str(token_payload.get("access_token") or "")
    if not access_token:
        raise HTTPException(status_code=500, detail="Failed to acquire Azure AD access token.")

    expires_in_raw = token_payload.get("expires_in")
    try:
        expires_in = int(expires_in_raw) if expires_in_raw is not None else 3600
    except (TypeError, ValueError):
        expires_in = 3600

    # Refresh a bit earlier to avoid using an almost-expired token.
    expires_at = time.time() + max(60, expires_in - _TOKEN_MIN_TTL_SECONDS)
    _TOKEN_CACHE["access_token"] = access_token
    _TOKEN_CACHE["expires_at"] = expires_at
    return access_token


def get_graph_access_token() -> str:
    cached = _read_cached_token()
    if cached:
        return cached

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

    with _TOKEN_LOCK:
        # Re-check inside lock to avoid duplicate token requests under concurrency.
        cached = _read_cached_token()
        if cached:
            return cached

        token = app_msal.acquire_token_silent(["https://graph.microsoft.com/.default"], account=None)
        if not token:
            token = app_msal.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

        if not isinstance(token, dict):
            logger.error("Failed to acquire Graph access token: %s", token)
            raise HTTPException(status_code=500, detail="Failed to acquire Azure AD access token.")

        try:
            return _write_cached_token(token)
        except HTTPException:
            logger.error("Failed to acquire Graph access token: %s", token)
            raise
