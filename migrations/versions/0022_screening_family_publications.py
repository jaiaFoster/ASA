"""Record exact atomic complete-family latest-state publications.

Revision ID: 0022
Revises: 0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "screening_family_publications",
        sa.Column("publication_id", sa.String(80), primary_key=True),
        sa.Column("family_id", sa.String(128), nullable=False),
        sa.Column("formation_date", sa.Date(), nullable=False),
        sa.Column("identity_version", sa.String(16), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("member_manifest", postgresql.JSONB(), nullable=False),
        sa.Column(
            "committed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "family_id", "formation_date", name="uq_screening_family_formation"
        ),
    )


def downgrade() -> None:
    op.drop_table("screening_family_publications")
