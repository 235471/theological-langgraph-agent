"""
Cache Service

Avoids reprocessing identical theological analyses.
Cache key = SHA-256 hash of (book + chapter + sorted_verses + sorted_modules).
"""

import hashlib
import json
from typing import Optional

from app.database.connection import get_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)


def generate_cache_key(
    book: str, chapter: int, verses: list[int], modules: list[str]
) -> str:
    """
    Generate a deterministic cache key from analysis parameters.

    Sorts verses and modules to ensure order-independence.
    """
    payload = json.dumps(
        {
            "book": book.strip().lower(),
            "chapter": chapter,
            "verses": sorted(verses),
            "modules": sorted(modules),
        },
        sort_keys=True,
    )

    return hashlib.sha256(payload.encode()).hexdigest()


def get_cached_analysis(cache_key: str) -> Optional[str]:
    """
    Look up a cached analysis by cache key.

    Returns the final_analysis text if found, None otherwise.
    Increments hit_count on cache hit.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE analysis_cache
                    SET hit_count = hit_count + 1
                    WHERE cache_key = %s
                    RETURNING final_analysis
                    """,
                    (cache_key,),
                )
                row = cur.fetchone()
            conn.commit()

        if row:
            logger.info(
                "Cache HIT",
                extra={"event": "cache_hit", "cache_key": cache_key[:12]},
            )
            return row[0]

        logger.info(
            "Cache MISS",
            extra={"event": "cache_miss", "cache_key": cache_key[:12]},
        )
        return None

    except Exception as e:
        logger.error(
            f"Cache lookup failed: {e}",
            extra={"event": "cache_error", "cache_key": cache_key[:12]},
        )
        return None


def save_to_cache(
    cache_key: str,
    book: str,
    chapter: int,
    verses: list[int],
    modules: list[str],
    final_analysis: str,
    run_id: str | None = None,
) -> None:
    """
    Save a completed analysis to cache.
    Uses ON CONFLICT DO NOTHING to handle race conditions.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analysis_cache
                        (cache_key, book, chapter, verses, selected_modules, final_analysis, run_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (cache_key) DO NOTHING
                    """,
                    (cache_key, book, chapter, verses, modules, final_analysis, run_id),
                )
            conn.commit()

        logger.info(
            "Analysis cached",
            extra={"event": "cache_write", "cache_key": cache_key[:12]},
        )

    except Exception as e:
        logger.error(
            f"Cache write failed: {e}",
            extra={"event": "cache_write_error", "cache_key": cache_key[:12]},
        )
