"""Add durable lifecycle state to external scheduler slots.

Revision ID: 0021
Revises: 0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("refresh_schedule_claims", "claimed_at", nullable=True)
    op.add_column(
        "refresh_schedule_claims",
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "refresh_schedule_claims",
        sa.Column(
            "operational_state",
            sa.String(length=32),
            nullable=False,
            server_default="DUE_UNOBSERVED",
        ),
    )
    op.add_column(
        "refresh_schedule_claims",
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "refresh_schedule_claims", sa.Column("reason_code", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "refresh_schedule_claims", sa.Column("failure_class", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "refresh_schedule_claims",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
    )
    # A legacy row proves admission only, not successful execution. Preserve
    # that uncertainty and make the old owner immediately reclaimable rather
    # than fabricating a completed evaluation during migration.
    op.execute(
        "UPDATE refresh_schedule_claims "
        "SET observed_at = claimed_at, claim_expires_at = claimed_at, "
        "operational_state = 'DUE_UNOBSERVED'"
    )
    op.alter_column("refresh_schedule_claims", "observed_at", nullable=False)
    op.create_check_constraint(
        "ck_refresh_schedule_operational_state",
        "refresh_schedule_claims",
        "operational_state IN ('NOT_DUE', 'DUE_UNOBSERVED', 'DUE_EVALUATED', "
        "'DUE_TYPED_DEFERRED', 'DUE_ASA_EXCEPTION')",
    )
    op.create_check_constraint(
        "ck_refresh_schedule_attempt_count",
        "refresh_schedule_claims",
        "attempt_count >= 0",
    )


def downgrade() -> None:
    # The old table represents acquired claims only. New projection-only
    # observations have no claim and cannot be represented in that schema.
    op.execute("DELETE FROM refresh_schedule_claims WHERE claimed_at IS NULL")
    op.drop_constraint(
        "ck_refresh_schedule_attempt_count", "refresh_schedule_claims", type_="check"
    )
    op.drop_constraint(
        "ck_refresh_schedule_operational_state", "refresh_schedule_claims", type_="check"
    )
    op.drop_column("refresh_schedule_claims", "attempt_count")
    op.drop_column("refresh_schedule_claims", "failure_class")
    op.drop_column("refresh_schedule_claims", "reason_code")
    op.drop_column("refresh_schedule_claims", "observed_at")
    op.drop_column("refresh_schedule_claims", "operational_state")
    op.drop_column("refresh_schedule_claims", "claim_expires_at")
    op.alter_column("refresh_schedule_claims", "claimed_at", nullable=False)
