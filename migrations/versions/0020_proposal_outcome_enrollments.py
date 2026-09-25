"""System-actionable proposal enrollments and their forward outcomes (ND-01).

Revision ID: 0020
Revises: 0019

Structurally separate from user tracking (``tracked_candidates``); nothing in
0016-0019 is altered. Downgrade drops the accumulated system forward corpus,
which cannot be regenerated; running it in production is a Founder-only
destructive action.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "proposal_outcome_enrollments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("enrollment_policy_version", sa.String(32), nullable=False),
        sa.Column("originating_observation_id", sa.String(128), nullable=False),
        sa.Column("opportunity_id", sa.String(128), nullable=True),
        sa.Column("signal_id", sa.String(64), nullable=False),
        sa.Column("signal_version", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("evidence_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_proposal_identity", sa.String(64), nullable=False),
        sa.Column("resolved_proposal_json", sa.Text(), nullable=False),
        sa.UniqueConstraint("resolved_proposal_identity", name="uq_proposal_enrollment_proposal"),
        sa.UniqueConstraint(
            "signal_id",
            "signal_version",
            "symbol",
            "session_date",
            name="uq_proposal_enrollment_session_slot",
        ),
        sa.CheckConstraint(
            "enrolled_at >= evidence_observed_at", name="ck_proposal_enrollment_time"
        ),
    )
    op.create_table(
        "enrolled_proposal_outcome_observations",
        sa.Column(
            "enrollment_id",
            sa.Uuid(),
            sa.ForeignKey("proposal_outcome_enrollments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("horizon_id", sa.String(32), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_policy_version", sa.String(32), nullable=False),
        sa.Column("frozen_proposal_identity", sa.String(64), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("underlying_price", sa.Numeric(), nullable=True),
        sa.Column("modeled_mark", sa.Numeric(), nullable=True),
        sa.Column("modeled_pnl", sa.Numeric(), nullable=True),
        sa.Column("mark_basis", sa.String(64), nullable=True),
        sa.Column("mark_model_version", sa.String(64), nullable=True),
        sa.Column("unknown_reasons_json", sa.Text(), nullable=False),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.Column("content_identity", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("enrollment_id", "horizon_id"),
        sa.CheckConstraint(
            "status IN ('observed', 'missed', 'not_observable_before_tracking')",
            name="ck_enrolled_outcome_status",
        ),
        sa.CheckConstraint(
            "(status = 'observed') = (observed_at IS NOT NULL)",
            name="ck_enrolled_outcome_observed_time",
        ),
    )


def downgrade() -> None:
    op.drop_table("enrolled_proposal_outcome_observations")
    op.drop_table("proposal_outcome_enrollments")
