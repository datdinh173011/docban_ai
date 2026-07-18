"""Use 384-dimensional local MiniLM vectors for procedure RAG."""

from alembic import op

revision = "20260718_08"
down_revision = "20260718_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX idx_procedure_chunk_embedding")
    op.execute("""
        ALTER TABLE procedure_chunk ALTER COLUMN embedding TYPE VECTOR(384)
        USING embedding::text::vector(384)
    """)
    op.execute("CREATE INDEX idx_procedure_chunk_embedding ON procedure_chunk USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX idx_procedure_chunk_embedding")
    op.execute("""
        ALTER TABLE procedure_chunk ALTER COLUMN embedding TYPE VECTOR(1536)
        USING embedding::text::vector(1536)
    """)
    op.execute("CREATE INDEX idx_procedure_chunk_embedding ON procedure_chunk USING hnsw (embedding vector_cosine_ops)")
