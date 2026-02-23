"""
Database Bootstrap Script

Idempotent table and index creation for Supabase PostgreSQL.
Run on application startup or manually via `python -m app.database.init_db`.
"""

from app.database.connection import get_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)

# --- Table Definitions (one per list item for PgBouncer compatibility) ---

TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS analysis_runs (
        id              SERIAL PRIMARY KEY,
        run_id          VARCHAR(36) NOT NULL UNIQUE,
        book            VARCHAR(10) NOT NULL,
        chapter         INTEGER NOT NULL,
        verses          INTEGER[] NOT NULL,
        selected_modules TEXT[] NOT NULL,
        model_versions  JSONB,
        prompt_versions JSONB,
        tokens_consumed JSONB,
        reasoning_steps JSONB,
        risk_level      VARCHAR(10),
        hitl_status     VARCHAR(20),
        final_analysis  TEXT,
        success         BOOLEAN NOT NULL DEFAULT TRUE,
        error           TEXT,
        duration_ms     INTEGER,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS analysis_cache (
        id              SERIAL PRIMARY KEY,
        cache_key       VARCHAR(64) NOT NULL UNIQUE,
        book            VARCHAR(10) NOT NULL,
        chapter         INTEGER NOT NULL,
        verses          INTEGER[] NOT NULL,
        selected_modules TEXT[] NOT NULL,
        final_analysis  TEXT NOT NULL,
        run_id          VARCHAR(36),
        hit_count       INTEGER NOT NULL DEFAULT 0,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS hitl_reviews (
        id               SERIAL PRIMARY KEY,
        run_id           VARCHAR(36) NOT NULL UNIQUE,
        book             VARCHAR(10) NOT NULL,
        chapter          INTEGER NOT NULL,
        verses           INTEGER[] NOT NULL,
        risk_level       VARCHAR(10) NOT NULL,
        alerts           TEXT[] NOT NULL DEFAULT '{}',
        validation_content TEXT,
        panorama_content   TEXT,
        lexical_content    TEXT,
        historical_content TEXT,
        intertextual_content TEXT,
        selected_modules TEXT[] NOT NULL,
        edited_content   TEXT,
        reviewer_email   VARCHAR(255),
        status           VARCHAR(20) NOT NULL DEFAULT 'pending',
        model_versions   JSONB,
        prompt_versions  JSONB,
        tokens_consumed  JSONB,
        reasoning_steps  JSONB,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        reviewed_at      TIMESTAMPTZ
    )
    """,
]

# --- Index Definitions (one per list item for PgBouncer compatibility) ---

INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_runs_created_at ON analysis_runs (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_runs_book_chapter ON analysis_runs (book, chapter)",
    "CREATE INDEX IF NOT EXISTS idx_runs_run_id ON analysis_runs (run_id)",
    "CREATE INDEX IF NOT EXISTS idx_cache_key ON analysis_cache (cache_key)",
    "CREATE INDEX IF NOT EXISTS idx_cache_book_chapter ON analysis_cache (book, chapter)",
    "CREATE INDEX IF NOT EXISTS idx_hitl_status ON hitl_reviews (status)",
    "CREATE INDEX IF NOT EXISTS idx_hitl_run_id ON hitl_reviews (run_id)",
    "CREATE INDEX IF NOT EXISTS idx_hitl_created_at ON hitl_reviews (created_at DESC)",
]


def init_database() -> bool:
    """
    Initialize database tables and indexes.
    Idempotent — safe to run multiple times.

    Each statement is executed individually for compatibility with
    Supabase Transaction Pooler (PgBouncer), which rejects
    multi-statement prepared queries.

    Returns:
        True if successful, False otherwise.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for sql in TABLES_SQL:
                    cur.execute(sql)
                for sql in INDEXES_SQL:
                    cur.execute(sql)
            conn.commit()

        logger.info(
            "Database tables and indexes initialized successfully",
            extra={"event": "db_init_success"},
        )
        return True

    except Exception as e:
        logger.error(
            f"Database initialization failed: {e}",
            extra={"event": "db_init_failed"},
        )
        return False


# Allow running directly: python -m app.database.init_db
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    init_database()
