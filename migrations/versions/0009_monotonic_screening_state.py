"""Add indexed source time used by monotonic latest-state writes.

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "universal_screening_state",
        sa.Column("source_observed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE universal_screening_state "
        "SET source_observed_at = observed_at "
        "WHERE source_observed_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("universal_screening_state", "source_observed_at")
