"""Separate canonical and fetch URLs for reviewed legal sources."""

from alembic import op

revision = "20260718_05"
down_revision = "20260718_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE official_source_registry RENAME COLUMN allowed_hostname TO allowed_canonical_hostname")
    op.execute("ALTER TABLE official_source_registry ALTER COLUMN canonical_url DROP NOT NULL")
    op.execute("ALTER TABLE official_source_registry ALTER COLUMN effective_from DROP NOT NULL")
    op.execute("ALTER TABLE official_source_registry ADD COLUMN fetch_url TEXT")
    op.execute("ALTER TABLE official_source_registry ADD COLUMN allowed_fetch_hostname TEXT")
    op.execute("ALTER TABLE official_source_registry ADD COLUMN allowed_redirect_hostnames TEXT[] NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE official_source_registry ADD COLUMN legal_status TEXT NOT NULL DEFAULT 'draft' CHECK (legal_status IN ('draft', 'active', 'amended', 'superseded', 'repealed', 'discovery'))")
    op.execute("ALTER TABLE official_source_registry ADD COLUMN amends_source_codes TEXT[] NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE official_source_registry ADD COLUMN supersedes_source_codes TEXT[] NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE official_source_registry ADD COLUMN official_verified_at TIMESTAMPTZ")
    op.execute("ALTER TABLE official_source_registry ADD COLUMN reviewer_id TEXT")
    op.execute("ALTER TABLE official_source_registry ADD COLUMN discovery_urls JSONB NOT NULL DEFAULT '[]'")
    op.execute("""
        UPDATE official_source_registry
        SET approval_status = 'retired', legal_status = 'draft', updated_at = now()
        WHERE source_code IN ('DECREE_CIVIL_STATUS_CURRENT', 'CIRCULAR_CIVIL_STATUS_CURRENT')
    """)
    op.execute("""
        ALTER TABLE official_source_registry ADD CONSTRAINT approved_legal_source_requires_review
        CHECK (
            approval_status <> 'approved' OR (
                canonical_url IS NOT NULL AND fetch_url IS NOT NULL
                AND allowed_canonical_hostname IS NOT NULL AND allowed_fetch_hostname IS NOT NULL
                AND official_verified_at IS NOT NULL AND reviewer_id IS NOT NULL
                AND effective_from IS NOT NULL
                AND legal_status IN ('active', 'amended')
                AND allowed_canonical_hostname <> 'thuvienphapluat.vn'
                AND allowed_fetch_hostname <> 'thuvienphapluat.vn'
            )
        )
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE official_source_registry DROP CONSTRAINT approved_legal_source_requires_review")
    op.execute("ALTER TABLE official_source_registry DROP COLUMN discovery_urls")
    op.execute("ALTER TABLE official_source_registry DROP COLUMN reviewer_id")
    op.execute("ALTER TABLE official_source_registry DROP COLUMN official_verified_at")
    op.execute("ALTER TABLE official_source_registry DROP COLUMN supersedes_source_codes")
    op.execute("ALTER TABLE official_source_registry DROP COLUMN amends_source_codes")
    op.execute("ALTER TABLE official_source_registry DROP COLUMN legal_status")
    op.execute("ALTER TABLE official_source_registry DROP COLUMN allowed_redirect_hostnames")
    op.execute("ALTER TABLE official_source_registry DROP COLUMN allowed_fetch_hostname")
    op.execute("ALTER TABLE official_source_registry DROP COLUMN fetch_url")
    op.execute("ALTER TABLE official_source_registry ALTER COLUMN canonical_url SET NOT NULL")
    op.execute("ALTER TABLE official_source_registry ALTER COLUMN effective_from SET NOT NULL")
    op.execute("ALTER TABLE official_source_registry RENAME COLUMN allowed_canonical_hostname TO allowed_hostname")
