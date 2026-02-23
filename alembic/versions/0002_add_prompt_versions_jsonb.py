"""add prompt_versions jsonb

Revision ID: 0002_add_prompt_versions_jsonb
Revises: 0001_baseline_init_schema
Create Date: 2026-02-23
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_add_prompt_versions_jsonb"
down_revision = "0001_baseline_init_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS prompt_versions JSONB"
    )
    op.execute(
        "ALTER TABLE hitl_reviews ADD COLUMN IF NOT EXISTS prompt_versions JSONB"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE hitl_reviews DROP COLUMN IF EXISTS prompt_versions")
    op.execute("ALTER TABLE analysis_runs DROP COLUMN IF EXISTS prompt_versions")

