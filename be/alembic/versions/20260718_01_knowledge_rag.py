"""Create the versioned knowledge schema used by the birth-registration RAG."""

from alembic import op

revision = "20260718_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    schema_statements = """
        CREATE TABLE administrative_area (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            area_code TEXT NOT NULL UNIQUE,
            name_vi TEXT NOT NULL,
            area_level TEXT NOT NULL CHECK (area_level IN ('province', 'district', 'ward')),
            parent_id UUID REFERENCES administrative_area(id),
            status TEXT NOT NULL DEFAULT 'active',
            effective_from DATE, effective_to DATE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE administrative_procedure (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            procedure_code TEXT NOT NULL UNIQUE, external_procedure_code TEXT,
            status TEXT NOT NULL DEFAULT 'active', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE procedure_version (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            procedure_id UUID NOT NULL REFERENCES administrative_procedure(id), version_no INTEGER NOT NULL,
            title_vi TEXT NOT NULL, jurisdiction_scope TEXT NOT NULL DEFAULT 'national' CHECK (jurisdiction_scope IN ('national', 'province', 'district')),
            administrative_area_id UUID REFERENCES administrative_area(id), effective_from DATE, effective_to DATE,
            status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'in_review', 'published', 'archived', 'rejected')),
            metadata JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (procedure_id, version_no),
            CHECK ((jurisdiction_scope = 'national' AND administrative_area_id IS NULL) OR (jurisdiction_scope <> 'national' AND administrative_area_id IS NOT NULL))
        );
        CREATE TABLE source_file (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), file_code TEXT NOT NULL UNIQUE, original_name TEXT NOT NULL,
            storage_path TEXT NOT NULL, mime_type TEXT NOT NULL, size_bytes BIGINT, sha256 TEXT NOT NULL,
            source_url TEXT, source_name TEXT, downloaded_at TIMESTAMPTZ, derived_from_file_id UUID REFERENCES source_file(id),
            file_status TEXT NOT NULL DEFAULT 'active', metadata JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE legal_source (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), source_code TEXT NOT NULL UNIQUE, source_type TEXT NOT NULL,
            issuing_authority_vi TEXT, document_number TEXT, title_vi TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE legal_source_version (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), legal_source_id UUID NOT NULL REFERENCES legal_source(id), version_no INTEGER NOT NULL,
            source_file_id UUID REFERENCES source_file(id), jurisdiction_scope TEXT NOT NULL DEFAULT 'national' CHECK (jurisdiction_scope IN ('national', 'province', 'district')),
            administrative_area_id UUID REFERENCES administrative_area(id), issued_date DATE, effective_from DATE, effective_to DATE,
            status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'in_review', 'published', 'archived', 'rejected')),
            source_url TEXT, extracted_text_path TEXT, metadata JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (legal_source_id, version_no),
            CHECK ((jurisdiction_scope = 'national' AND administrative_area_id IS NULL) OR (jurisdiction_scope <> 'national' AND administrative_area_id IS NOT NULL))
        );
        CREATE TABLE knowledge_document (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), document_code TEXT NOT NULL UNIQUE,
            legal_source_version_id UUID REFERENCES legal_source_version(id), procedure_version_id UUID REFERENCES procedure_version(id),
            jurisdiction_scope TEXT NOT NULL DEFAULT 'national' CHECK (jurisdiction_scope IN ('national', 'province', 'district')),
            administrative_area_id UUID REFERENCES administrative_area(id), document_type TEXT NOT NULL, language_code TEXT NOT NULL DEFAULT 'vi',
            title TEXT NOT NULL, normalized_text_path TEXT, status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'in_review', 'published', 'archived', 'rejected')),
            metadata JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK ((jurisdiction_scope = 'national' AND administrative_area_id IS NULL) OR (jurisdiction_scope <> 'national' AND administrative_area_id IS NOT NULL))
        );
        CREATE TABLE knowledge_chunk (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), knowledge_document_id UUID NOT NULL REFERENCES knowledge_document(id) ON DELETE CASCADE,
            chunk_no INTEGER NOT NULL, chunk_type TEXT NOT NULL, hierarchy_path JSONB NOT NULL DEFAULT '[]', title TEXT, content TEXT NOT NULL,
            token_count INTEGER NOT NULL, text_search TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
            embedding VECTOR(1536), jurisdiction_scope TEXT NOT NULL DEFAULT 'national' CHECK (jurisdiction_scope IN ('national', 'province', 'district')),
            administrative_area_id UUID REFERENCES administrative_area(id), metadata JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (knowledge_document_id, chunk_no),
            CHECK ((jurisdiction_scope = 'national' AND administrative_area_id IS NULL) OR (jurisdiction_scope <> 'national' AND administrative_area_id IS NOT NULL))
        );
        CREATE INDEX idx_knowledge_document_filter ON knowledge_document (status, language_code, jurisdiction_scope, administrative_area_id, procedure_version_id);
        CREATE INDEX idx_knowledge_chunk_document ON knowledge_chunk (knowledge_document_id, chunk_no);
        CREATE INDEX idx_knowledge_chunk_text_search ON knowledge_chunk USING GIN (text_search);
        CREATE INDEX idx_knowledge_chunk_embedding_hnsw ON knowledge_chunk USING hnsw (embedding vector_cosine_ops);
    """
    for statement in schema_statements.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge_chunk, knowledge_document, legal_source_version, legal_source, source_file, procedure_version, administrative_procedure, administrative_area CASCADE")
