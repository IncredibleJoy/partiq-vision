"""add token usage tracking

Revision ID: 20260825_0002
Revises: 20260825_0001
Create Date: 2026-08-25
"""

from alembic import op


revision = "20260825_0002"
down_revision = "20260825_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().exec_driver_sql(
        """
        ALTER TABLE analysis_jobs
        ADD COLUMN IF NOT EXISTS token_usage JSONB NOT NULL
        DEFAULT '{"items":[],"total_input_tokens":0,"total_output_tokens":0,"total_tokens":0}'::jsonb
        """
    )


def downgrade() -> None:
    op.get_bind().exec_driver_sql("ALTER TABLE analysis_jobs DROP COLUMN IF EXISTS token_usage")
