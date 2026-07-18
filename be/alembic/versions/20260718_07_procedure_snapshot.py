"""Add versioned DVC procedure snapshot storage for production RAG."""

from alembic import op

revision = "20260718_07"
down_revision = "20260718_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE procedure_snapshot (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), snapshot_code TEXT NOT NULL UNIQUE,
            crawled_at TIMESTAMPTZ NOT NULL, source_path TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'published', 'archived')),
            procedure_count INTEGER NOT NULL, manifest_sha256 TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE procedure_catalog (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), snapshot_id UUID NOT NULL REFERENCES procedure_snapshot(id) ON DELETE CASCADE,
            procedure_code TEXT NOT NULL, title TEXT NOT NULL, group_name TEXT NOT NULL, field_name TEXT NOT NULL,
            request_type TEXT NOT NULL, scenario TEXT NOT NULL, locality TEXT NOT NULL, scope TEXT NOT NULL,
            execution_level TEXT NOT NULL, issuing_authority TEXT NOT NULL, receiving_authority TEXT NOT NULL,
            decision_number TEXT, pdf_path TEXT NOT NULL, pdf_sha256 TEXT NOT NULL, data_warning TEXT NOT NULL,
            UNIQUE(snapshot_id, procedure_code)
        )
    """)
    op.execute("""
        CREATE TABLE procedure_chunk (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), procedure_id UUID NOT NULL REFERENCES procedure_catalog(id) ON DELETE CASCADE,
            chunk_no INTEGER NOT NULL, section_type TEXT NOT NULL, section_title TEXT NOT NULL, page_no INTEGER,
            content TEXT NOT NULL, normalized_content TEXT NOT NULL, embedding VECTOR(1536), review_status TEXT NOT NULL DEFAULT 'snapshot'
                CHECK (review_status IN ('snapshot', 'reviewed')), UNIQUE(procedure_id, chunk_no)
        )
    """)
    op.execute("""
        CREATE INDEX idx_procedure_catalog_lookup ON procedure_catalog (snapshot_id, procedure_code, locality, scope);
    """)
    op.execute("""
        CREATE INDEX idx_procedure_chunk_fts ON procedure_chunk USING GIN (to_tsvector('simple', normalized_content));
    """)
    op.execute("""
        CREATE INDEX idx_procedure_chunk_embedding ON procedure_chunk USING hnsw (embedding vector_cosine_ops);
    """)
    op.execute("""
        CREATE TABLE procedure_form_candidate (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), snapshot_id UUID NOT NULL REFERENCES procedure_snapshot(id) ON DELETE CASCADE,
            filename TEXT NOT NULL, relative_path TEXT NOT NULL, sha256 TEXT NOT NULL, source_procedure_id TEXT,
            component_name TEXT, procedure_id UUID REFERENCES procedure_catalog(id), review_status TEXT NOT NULL DEFAULT 'snapshot'
                CHECK (review_status IN ('snapshot', 'reviewed')), UNIQUE(snapshot_id, relative_path)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE procedure_form_candidate, procedure_chunk, procedure_catalog, procedure_snapshot")
