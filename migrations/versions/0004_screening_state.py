"""Create screening_state -- current, latest-only screening results.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "screening_state",
        sa.Column("signal_id", sa.String(length=64), primary_key=True),
        sa.Column("symbol", sa.String(length=32), primary_key=True),
        sa.Column("signal_version", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dependency_timestamps", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("screening_state")
