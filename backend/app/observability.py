from __future__ import annotations

import json
import logging
import os
import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any

_REQUEST_ID_CTX: ContextVar[str] = ContextVar("request_id", default="-")
_RESERVED_RECORD_KEYS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


def get_request_id() -> str:
    return _REQUEST_ID_CTX.get("-")


def set_request_id(request_id: str) -> Token[str]:
    normalized = str(request_id or "").strip() or "-"
    return _REQUEST_ID_CTX.set(normalized)


def reset_request_id(token: Token[str]) -> None:
    _REQUEST_ID_CTX.reset(token)


def generate_request_id() -> str:
    return uuid.uuid4().hex[:16]


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    return str(value)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", get_request_id()),
        }

        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_KEYS or key.startswith("_"):
                continue
            if key in payload:
                continue
            payload[key] = _to_jsonable(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    logger = logging.getLogger("bom_api")
    if getattr(logger, "_bom_configured", False):
        return

    log_level_name = str(os.getenv("BOM_LOG_LEVEL", "INFO") or "INFO").upper()
    level = getattr(logging, log_level_name, logging.INFO)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(RequestIdFilter())

    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    logger._bom_configured = True
