from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from alembic import command
from alembic.config import Config
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings


pool = ConnectionPool(conninfo=settings.database_url, kwargs={"row_factory": dict_row}, open=False)


def sqlalchemy_database_url() -> str:
    if settings.database_url.startswith("postgresql://"):
        return settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return settings.database_url


def start_pool() -> None:
    pool.open()


def close_pool() -> None:
    pool.close()


def run_migrations() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", sqlalchemy_database_url())
    command.upgrade(config, "head")


@contextmanager
def get_conn() -> Iterator[Connection]:
    with pool.connection() as conn:
        yield conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_metadata (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_jobs (
              id UUID PRIMARY KEY,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              model_mode TEXT NOT NULL,
              vehicle_context TEXT NOT NULL,
              token_usage JSONB NOT NULL DEFAULT '{"items":[],"total_input_tokens":0,"total_output_tokens":0,"total_tokens":0}'::jsonb
            )
            """
        )
        conn.execute(
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS part_vectors (
              detection_id UUID PRIMARY KEY REFERENCES detections(id) ON DELETE CASCADE,
              job_id UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
              content TEXT NOT NULL,
              embedding vector(1536) NOT NULL
            )
            """
        )
        conn.execute(
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
        conn.execute(
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
        conn.execute(
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_part_vectors (
              sku TEXT PRIMARY KEY REFERENCES warehouse_parts(sku) ON DELETE CASCADE,
              embedding vector(1536) NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS part_vectors_embedding_idx
            ON part_vectors USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 50)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS warehouse_part_vectors_embedding_idx
            ON warehouse_part_vectors USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 75)
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS warehouse_parts_cluster_idx ON warehouse_parts (cluster_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS warehouse_parts_system_idx ON warehouse_parts (vehicle_system)")
        conn.execute("CREATE INDEX IF NOT EXISTS warehouse_parts_category_idx ON warehouse_parts (category)")
        conn.commit()
