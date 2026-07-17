"""Add trusted form-source registry and canonical form schema."""

from alembic import op

revision = "20260718_03"
down_revision = "20260718_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE source_registry (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_key TEXT NOT NULL,
            version_no INTEGER NOT NULL,
            canonical_path TEXT NOT NULL,
            snapshot_path TEXT NOT NULL,
            normalized_text_path TEXT NOT NULL,
            source_trust_tier TEXT NOT NULL CHECK (
                source_trust_tier IN ('operator_verified_primary', 'reviewed', 'external')
            ),
            asset_kind TEXT NOT NULL CHECK (asset_kind IN ('form_pdf', 'inventory_pdf', 'bundle_pdf')),
            form_code TEXT,
            form_role TEXT NOT NULL CHECK (form_role IN ('primary_form', 'reference_support', 'inventory', 'bundle')),
            form_number TEXT,
            legal_source_reference TEXT,
            jurisdiction_scope TEXT NOT NULL DEFAULT 'national',
            administrative_area_id UUID REFERENCES administrative_area(id),
            parser_profile TEXT NOT NULL,
            expected_field_groups JSONB NOT NULL DEFAULT '[]',
            sha256 TEXT NOT NULL,
            page_count INTEGER NOT NULL,
            effective_from DATE,
            effective_to DATE,
            imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'in_review', 'published', 'archived')),
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            , UNIQUE (source_key, version_no)
        )
    """)
    op.execute("""
        CREATE TABLE form_template (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            form_code TEXT NOT NULL UNIQUE,
            title_vi TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'in_review', 'published', 'archived')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE form_version (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            form_template_id UUID NOT NULL REFERENCES form_template(id),
            source_registry_id UUID NOT NULL REFERENCES source_registry(id),
            version_no INTEGER NOT NULL,
            form_role TEXT NOT NULL CHECK (form_role IN ('primary_form', 'reference_support')),
            effective_from DATE,
            effective_to DATE,
            status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'in_review', 'published', 'archived')),
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (form_template_id, version_no)
        )
    """)
    op.execute("""
        CREATE TABLE form_section (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            form_version_id UUID NOT NULL REFERENCES form_version(id) ON DELETE CASCADE,
            section_code TEXT NOT NULL,
            title_vi TEXT NOT NULL,
            page_start INTEGER NOT NULL,
            page_end INTEGER NOT NULL,
            display_order INTEGER NOT NULL,
            UNIQUE (form_version_id, section_code)
        )
    """)
    op.execute("""
        CREATE TABLE form_field (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            form_version_id UUID NOT NULL REFERENCES form_version(id) ON DELETE CASCADE,
            section_id UUID REFERENCES form_section(id) ON DELETE SET NULL,
            field_code TEXT NOT NULL,
            label_vi TEXT NOT NULL,
            data_type TEXT NOT NULL,
            required BOOLEAN NOT NULL DEFAULT false,
            page_no INTEGER NOT NULL,
            provenance JSONB NOT NULL DEFAULT '{}',
            field_config JSONB NOT NULL DEFAULT '{}',
            UNIQUE (form_version_id, field_code)
        )
    """)
    op.execute("""
        CREATE TABLE form_conditional_document (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            primary_form_code TEXT NOT NULL,
            support_form_code TEXT NOT NULL,
            condition_code TEXT NOT NULL,
            legal_rule_reference TEXT,
            status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'in_review', 'published', 'archived')),
            metadata JSONB NOT NULL DEFAULT '{}',
            UNIQUE (primary_form_code, support_form_code, condition_code)
        )
    """)
    op.execute("CREATE INDEX idx_source_registry_publish ON source_registry (status, source_trust_tier, form_code)")


def downgrade() -> None:
    op.execute("DROP TABLE form_conditional_document")
    op.execute("DROP TABLE form_field")
    op.execute("DROP TABLE form_section")
    op.execute("DROP TABLE form_version")
    op.execute("DROP TABLE form_template")
    op.execute("DROP TABLE source_registry")
