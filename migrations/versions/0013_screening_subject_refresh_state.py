"""Add durable oldest-first screening subject refresh state.

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "screening_subject_refresh_state",
        sa.Column("subject_id", sa.String(length=64), primary_key=True),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eligible_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("consecutive_failures >= 0", name="ck_subject_refresh_failures"),
    )
    op.create_index(
        "ix_subject_refresh_oldest",
        "screening_subject_refresh_state",
        ["last_completed_at", "subject_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_subject_refresh_oldest", table_name="screening_subject_refresh_state")
    op.drop_table("screening_subject_refresh_state")
