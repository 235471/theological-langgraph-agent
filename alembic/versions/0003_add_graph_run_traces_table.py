"""add graph_run_traces table

Revision ID: 0003_add_graph_run_traces_table
Revises: 0002_add_prompt_versions_jsonb
Create Date: 2026-02-27
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_add_graph_run_traces_table"
down_revision = "0002_add_prompt_versions_jsonb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS graph_run_traces (
            id               SERIAL PRIMARY KEY,
            run_id           VARCHAR(36) NOT NULL UNIQUE
                                 REFERENCES analysis_runs (run_id) ON DELETE CASCADE,
            langsmith_run_id VARCHAR(36),
            storage_path     TEXT,
            size_bytes       INTEGER,
            status           VARCHAR(20) NOT NULL,
            error_message    TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT graph_run_traces_status_check
                CHECK (status IN ('uploaded', 'failed', 'skipped'))
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_graph_run_traces_created_at "
        "ON graph_run_traces (created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_graph_run_traces_status "
        "ON graph_run_traces (status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_graph_run_traces_langsmith_run_id "
        "ON graph_run_traces (langsmith_run_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS graph_run_traces")
