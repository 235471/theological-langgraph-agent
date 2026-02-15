"""
PostgreSQL Connection Pool

Uses psycopg (already in requirements) with DB_URL from .env.
Provides a connection pool for cache, audit, and HITL persistence.
"""

import os
import psycopg
from psycopg_pool import ConnectionPool
from app.utils.logger import get_logger

logger = get_logger(__name__)

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Get or create the connection pool (lazy singleton)."""
    global _pool
    if _pool is None:
        db_url = os.getenv("DB_URL")
        if not db_url:
            raise ValueError("DB_URL not found in environment. Check your .env file.")

        _pool = ConnectionPool(
            conninfo=db_url,
            min_size=1,
            max_size=5,
            open=True,
            kwargs={
                "prepare_threshold": None
            },  # Disable prepared statements for Supabase Transaction Pooler
        )
        logger.info(
            "Database connection pool created (prepare_threshold=None for Supabase Pooler)",
            extra={"event": "db_pool_created"},
        )

    return _pool


def get_connection():
    """
    Get a connection from the pool (context manager).

    Usage:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    return get_pool().connection()


def check_db_health() -> bool:
    """Check if the database is reachable."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return True
    except Exception as e:
        logger.error(
            f"Database health check failed: {e}", extra={"event": "db_health_failed"}
        )
        return False


def close_pool() -> None:
    """Close the connection pool (call on shutdown)."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
        logger.info(
            "Database connection pool closed", extra={"event": "db_pool_closed"}
        )
