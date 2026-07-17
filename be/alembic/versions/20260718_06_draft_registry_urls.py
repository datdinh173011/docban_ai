"""Allow draft legal-source records before official URLs are reviewed."""

from alembic import op

revision = "20260718_06"
down_revision = "20260718_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE official_source_registry ALTER COLUMN allowed_canonical_hostname DROP NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE official_source_registry ALTER COLUMN allowed_canonical_hostname SET NOT NULL")
