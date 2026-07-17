"""Add approved legal-source registry and immutable knowledge packages."""

from alembic import op

revision = "20260718_04"
down_revision = "20260718_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE official_source_registry (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_code TEXT NOT NULL UNIQUE,
            canonical_url TEXT NOT NULL,
            allowed_hostname TEXT NOT NULL,
            issuing_authority_vi TEXT NOT NULL,
            document_number TEXT,
            title_vi TEXT NOT NULL,
            source_type TEXT NOT NULL,
            procedure_code TEXT NOT NULL,
            scenario_code TEXT NOT NULL DEFAULT 'STANDARD',
            jurisdiction_scope TEXT NOT NULL DEFAULT 'national'
                CHECK (jurisdiction_scope = 'national'),
            effective_from DATE NOT NULL,
            effective_to DATE,
            owner TEXT NOT NULL,
            check_cadence_days INTEGER NOT NULL CHECK (check_cadence_days > 0),
            parser_profile TEXT NOT NULL,
            approval_status TEXT NOT NULL DEFAULT 'draft'
                CHECK (approval_status IN ('draft', 'approved', 'retired')),
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK (effective_to IS NULL OR effective_to >= effective_from)
        )
    """)
    op.execute("""
        CREATE TABLE knowledge_package (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            package_code TEXT NOT NULL,
            version_no INTEGER NOT NULL,
            procedure_code TEXT NOT NULL,
            scenario_code TEXT NOT NULL DEFAULT 'STANDARD',
            jurisdiction_scope TEXT NOT NULL DEFAULT 'national'
                CHECK (jurisdiction_scope = 'national'),
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'in_review', 'published', 'archived', 'rejected')),
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            published_at TIMESTAMPTZ,
            UNIQUE (package_code, version_no)
        )
    """)
    op.execute("ALTER TABLE procedure_version ADD COLUMN knowledge_package_id UUID REFERENCES knowledge_package(id)")
    op.execute("CREATE INDEX idx_official_source_registry_approval ON official_source_registry (approval_status, procedure_code)")
    op.execute("CREATE INDEX idx_knowledge_package_status ON knowledge_package (package_code, status)")


def downgrade() -> None:
    op.execute("ALTER TABLE procedure_version DROP COLUMN knowledge_package_id")
    op.execute("DROP TABLE knowledge_package")
    op.execute("DROP TABLE official_source_registry")
