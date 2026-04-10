from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MAX_UPLOAD_BYTES = int(os.getenv("BOM_MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
ALLOWED_SAVE_FILE_EXTENSIONS = {".xlsx", ".csv"}
LOCAL_ORIGIN_REGEX = os.getenv(
    "BOM_ALLOWED_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
)
DATABASE_URL = os.getenv(
    "BOM_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/bom_platform",
)
DB_POOL_MIN_SIZE = int(os.getenv("BOM_DB_POOL_MIN_SIZE", "1"))
DB_POOL_MAX_SIZE = int(os.getenv("BOM_DB_POOL_MAX_SIZE", "10"))
FILE_STORAGE_DIR = Path(
    os.getenv(
        "BOM_FILE_STORAGE_DIR",
        str(Path(__file__).resolve().parents[1] / "data" / "bom_files"),
    )
)


def get_allowed_origins() -> list[str]:
    raw = os.getenv("BOM_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]
