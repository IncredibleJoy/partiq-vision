"""initial PartIQ Vision schema

Revision ID: 20260825_0001
Revises:
Create Date: 2026-08-25
"""

from alembic import op


revision = "20260825_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app_metadata (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_jobs (
          id UUID PRIMARY KEY,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          model_mode TEXT NOT NULL,
          vehicle_context TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS detections (
          id UUID PRIMARY KEY,
          job_id UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
          source_image TEXT NOT NULL,
          part_name TEXT NOT NULL,
          category TEXT NOT NULL,
          material TEXT NOT NULL,
          condition TEXT NOT NULL,
          visible_part_no TEXT,
          minute_details TEXT NOT NULL,
          confidence DOUBLE PRECISION NOT NULL,
          bbox JSONB NOT NULL,
          crop_url TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS part_vectors (
          detection_id UUID PRIMARY KEY REFERENCES detections(id) ON DELETE CASCADE,
          job_id UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
          content TEXT NOT NULL,
          embedding vector(1536) NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendations (
          id UUID PRIMARY KEY,
          job_id UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
          part_name TEXT NOT NULL,
          reason TEXT NOT NULL,
          recommendation_type TEXT NOT NULL,
          confidence DOUBLE PRECISION NOT NULL,
          related_parts JSONB NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_traces (
          id BIGSERIAL PRIMARY KEY,
          job_id UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
          agent TEXT NOT NULL,
          action TEXT NOT NULL,
          status TEXT NOT NULL,
          detail TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse_parts (
          sku TEXT PRIMARY KEY,
          part_name TEXT NOT NULL,
          category TEXT NOT NULL,
          vehicle_system TEXT NOT NULL,
          material TEXT NOT NULL,
          material_grade TEXT NOT NULL,
          condition_baseline TEXT NOT NULL,
          unit_cost NUMERIC(12, 2) NOT NULL,
          currency TEXT NOT NULL DEFAULT 'USD',
          stock_quantity INTEGER NOT NULL,
          reorder_level INTEGER NOT NULL,
          supplier TEXT NOT NULL,
          cluster_key TEXT NOT NULL,
          visible_part_nos JSONB NOT NULL,
          aliases JSONB NOT NULL,
          compatible_positions JSONB NOT NULL,
          minute_details TEXT NOT NULL,
          included_subparts JSONB NOT NULL,
          consumables_required JSONB NOT NULL,
          fitment_notes TEXT NOT NULL,
          embedding_content TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse_part_vectors (
          sku TEXT PRIMARY KEY REFERENCES warehouse_parts(sku) ON DELETE CASCADE,
          embedding vector(1536) NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS part_vectors_embedding_idx
        ON part_vectors USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 50)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS warehouse_part_vectors_embedding_idx
        ON warehouse_part_vectors USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 75)
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS warehouse_parts_cluster_idx ON warehouse_parts (cluster_key)")
    op.execute("CREATE INDEX IF NOT EXISTS warehouse_parts_system_idx ON warehouse_parts (vehicle_system)")
    op.execute("CREATE INDEX IF NOT EXISTS warehouse_parts_category_idx ON warehouse_parts (category)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS warehouse_parts_category_idx")
    op.execute("DROP INDEX IF EXISTS warehouse_parts_system_idx")
    op.execute("DROP INDEX IF EXISTS warehouse_parts_cluster_idx")
    op.execute("DROP INDEX IF EXISTS warehouse_part_vectors_embedding_idx")
    op.execute("DROP INDEX IF EXISTS part_vectors_embedding_idx")
    op.execute("DROP TABLE IF EXISTS warehouse_part_vectors")
    op.execute("DROP TABLE IF EXISTS warehouse_parts")
    op.execute("DROP TABLE IF EXISTS agent_traces")
    op.execute("DROP TABLE IF EXISTS recommendations")
    op.execute("DROP TABLE IF EXISTS part_vectors")
    op.execute("DROP TABLE IF EXISTS detections")
    op.execute("DROP TABLE IF EXISTS analysis_jobs")
    op.execute("DROP TABLE IF EXISTS app_metadata")
