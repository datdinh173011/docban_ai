"""Add versioned structured procedure facts for RAG queries."""

from alembic import op

revision = "20260718_02"
down_revision = "20260718_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE procedure_fact (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            procedure_version_id UUID NOT NULL REFERENCES procedure_version(id),
            fact_type TEXT NOT NULL,
            value JSONB NOT NULL,
            jurisdiction_scope TEXT NOT NULL DEFAULT 'national'
                CHECK (jurisdiction_scope IN ('national', 'province', 'district')),
            administrative_area_id UUID REFERENCES administrative_area(id),
            effective_from DATE,
            effective_to DATE,
            legal_source_version_id UUID REFERENCES legal_source_version(id),
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'in_review', 'published', 'archived', 'rejected')),
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK (
                (jurisdiction_scope = 'national' AND administrative_area_id IS NULL)
                OR (jurisdiction_scope <> 'national' AND administrative_area_id IS NOT NULL)
            )
        )
    """)
    op.execute("""
        CREATE INDEX idx_procedure_fact_retrieval ON procedure_fact (
            procedure_version_id, fact_type, status, jurisdiction_scope,
            administrative_area_id, effective_from, effective_to
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE procedure_fact")
