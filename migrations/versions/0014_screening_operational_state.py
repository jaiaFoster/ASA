"""Add singleton screening batch-operability state.

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "screening_operational_state",
        sa.Column("singleton_id", sa.Integer(), primary_key=True),
        sa.Column("last_attempted_batch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_batch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_batch_subject_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_batch_pair_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_batch_failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_batch_incomplete_diagnostic_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.CheckConstraint("singleton_id = 1", name="ck_screening_operational_singleton"),
    )
    op.execute("INSERT INTO screening_operational_state (singleton_id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("screening_operational_state")
