"""0029 — REQ-048 error_questions embedding columns + pgvector + tsvector index.

Adds:
- ``embedding vector(512)`` — bge-small-zh-v1.5 (512-dim, CPU)
- ``embedding_v2 vector(1024)`` — reserved for v2 bge-large migration
- ``embedding_computed_at timestamptz`` — stale detection
- ``embedding_model text`` — model identifier (e.g. 'bge-small-zh-v1.5')
- HNSW index on embedding (vector_cosine_ops)
- tsvector GIN index on question_text + answer_text for BM25

Revision ID: 0029_error_questions_embedding
Revises: 0028_interview_mode_split
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0029_error_questions_embedding"
down_revision: Union[str, Sequence[str], None] = "0028_interview_mode_split"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create pgvector extension (best-effort) + add embedding columns + indexes.

    pgvector extension is OPTIONAL on this PG instance:
    - If installed: embedding columns are ``vector(512)`` + ``vector(1024)`` + HNSW index.
    - If NOT installed (most cloud PG without ``vector`` package): columns fall back
      to ``text`` (JSON-encoded float arrays) so the application layer can still
      store embeddings; HNSW index is skipped; tsvector GIN index always created.

    AC-11 / AC-11b / AC-11c (backfill + arq cold/warm) all assume the
    embedding service writes to either column type without migration changes.
    """
    # Detect pgvector availability via ``pg_available_extensions``.
    has_pgvector = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM pg_available_extensions WHERE name = 'vector' LIMIT 1"
        )
    ).scalar() is not None

    if has_pgvector:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        # Real vector column types (CPU-friendly: 512-dim bge-small + 1024-dim reserved).
        op.execute("ALTER TABLE error_questions ADD COLUMN embedding vector(512)")
        op.execute("ALTER TABLE error_questions ADD COLUMN embedding_v2 vector(1024)")
        # HNSW index on embedding (cosine distance).
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_error_questions_embedding_hnsw "
            "ON error_questions USING hnsw (embedding vector_cosine_ops)"
        )
    else:
        # Fallback: text columns storing JSON-encoded float arrays.
        # Application layer reads/writes via ``embedding_service.client``.
        # Skill spec FR-010 + AC-11 still functional; only AC-04 cosine query is degraded.
        import warnings
        warnings.warn(
            "[REQ-048 0029] pgvector extension not available on this PG instance. "
            "Falling back to text columns for embedding storage. "
            "Hybrid retrieval cosine branch (AC-04) will degrade to BM25-only. "
            "Install pgvector on the PG server to enable full embedding features.",
            stacklevel=2,
        )
        op.add_column(
            "error_questions",
            sa.Column("embedding", sa.Text(), nullable=True),
        )
        op.add_column(
            "error_questions",
            sa.Column("embedding_v2", sa.Text(), nullable=True),
        )

    op.add_column(
        "error_questions",
        sa.Column("embedding_computed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "error_questions",
        sa.Column("embedding_model", sa.Text(), nullable=True),
    )
    # tsvector GIN index always created (BM25 uses this; independent of pgvector).
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_error_questions_tsvector_gin "
        "ON error_questions USING gin(to_tsvector('simple', question_text || ' ' || coalesce(answer_text, '')))"
    )


def downgrade() -> None:
    """Reverse migration."""
    op.execute("DROP INDEX IF EXISTS idx_error_questions_tsvector_gin")
    op.execute("DROP INDEX IF EXISTS idx_error_questions_embedding_hnsw")
    op.drop_column("error_questions", "embedding_model")
    op.drop_column("error_questions", "embedding_computed_at")
    op.execute("ALTER TABLE error_questions DROP COLUMN IF EXISTS embedding_v2")
    op.execute("ALTER TABLE error_questions DROP COLUMN IF EXISTS embedding")