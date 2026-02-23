"""baseline init schema

Revision ID: 0001_baseline_init_schema
Revises:
Create Date: 2026-02-23
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_baseline_init_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_runs (
            id               SERIAL PRIMARY KEY,
            run_id           VARCHAR(36) NOT NULL UNIQUE,
            book             VARCHAR(10) NOT NULL,
            chapter          INTEGER NOT NULL,
            verses           INTEGER[] NOT NULL,
            selected_modules TEXT[] NOT NULL,
            model_versions   JSONB,
            tokens_consumed  JSONB,
            reasoning_steps  JSONB,
            risk_level       VARCHAR(10),
            hitl_status      VARCHAR(20),
            final_analysis   TEXT,
            success          BOOLEAN NOT NULL DEFAULT TRUE,
            error            TEXT,
            duration_ms      INTEGER,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_cache (
            id               SERIAL PRIMARY KEY,
            cache_key        VARCHAR(64) NOT NULL UNIQUE,
            book             VARCHAR(10) NOT NULL,
            chapter          INTEGER NOT NULL,
            verses           INTEGER[] NOT NULL,
            selected_modules TEXT[] NOT NULL,
            final_analysis   TEXT NOT NULL,
            run_id           VARCHAR(36),
            hit_count        INTEGER NOT NULL DEFAULT 0,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hitl_reviews (
            id                  SERIAL PRIMARY KEY,
            run_id              VARCHAR(36) NOT NULL UNIQUE,
            book                VARCHAR(10) NOT NULL,
            chapter             INTEGER NOT NULL,
            verses              INTEGER[] NOT NULL,
            risk_level          VARCHAR(10) NOT NULL,
            alerts              TEXT[] NOT NULL DEFAULT '{}',
            validation_content  TEXT,
            panorama_content    TEXT,
            lexical_content     TEXT,
            historical_content  TEXT,
            intertextual_content TEXT,
            selected_modules    TEXT[] NOT NULL,
            edited_content      TEXT,
            reviewer_email      VARCHAR(255),
            status              VARCHAR(20) NOT NULL DEFAULT 'pending',
            model_versions      JSONB,
            tokens_consumed     JSONB,
            reasoning_steps     JSONB,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            reviewed_at         TIMESTAMPTZ
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_runs_created_at ON analysis_runs (created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_runs_book_chapter ON analysis_runs (book, chapter)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_runs_run_id ON analysis_runs (run_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cache_key ON analysis_cache (cache_key)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cache_book_chapter ON analysis_cache (book, chapter)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_hitl_status ON hitl_reviews (status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_hitl_run_id ON hitl_reviews (run_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_hitl_created_at ON hitl_reviews (created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hitl_reviews")
    op.execute("DROP TABLE IF EXISTS analysis_cache")
    op.execute("DROP TABLE IF EXISTS analysis_runs")

