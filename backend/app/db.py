from __future__ import annotations

import logging
from typing import Any

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

try:
    from psycopg_pool import ConnectionPool
except ImportError:
    ConnectionPool = None

from .config import DATABASE_URL, DB_POOL_MAX_SIZE, DB_POOL_MIN_SIZE

logger = logging.getLogger("bom_api")
_db_pool: Any | None = None


def require_psycopg() -> None:
    if psycopg is None:
        raise RuntimeError("psycopg is not installed. Install it with: pip install psycopg[binary]")


def init_db_pool() -> None:
    global _db_pool

    require_psycopg()
    if _db_pool is not None:
        return

    if ConnectionPool is None:
        logger.warning("psycopg_pool is not installed. Falling back to per-request DB connections.")
        return

    _db_pool = ConnectionPool(
        conninfo=DATABASE_URL,
        min_size=DB_POOL_MIN_SIZE,
        max_size=DB_POOL_MAX_SIZE,
        kwargs={"row_factory": dict_row},
        open=True,
    )
    logger.info("Database connection pool initialized (min=%s, max=%s).", DB_POOL_MIN_SIZE, DB_POOL_MAX_SIZE)


def close_db_pool() -> None:
    global _db_pool

    if _db_pool is None:
        return

    _db_pool.close()
    _db_pool = None
    logger.info("Database connection pool closed.")


def get_db_connection():
    require_psycopg()

    if _db_pool is not None:
        return _db_pool.connection()

    return psycopg.connect(DATABASE_URL, row_factory=dict_row)
