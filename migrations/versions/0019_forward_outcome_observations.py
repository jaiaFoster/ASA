"""Append-only forward outcome ledger (OUTCOME-INTELLIGENCE OI-04).

Revision ID: 0019
Revises: 0018

Downgrade drops accumulated forward evidence, which cannot be regenerated;
running it in production is a Founder-only destructive action.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forward_outcome_observations",
        sa.Column(
            "tracked_candidate_id",
            sa.Uuid(),
            sa.ForeignKey("tracked_candidates.id", ondelete="RESTRICT"),
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
        sa.PrimaryKeyConstraint("tracked_candidate_id", "horizon_id"),
        sa.CheckConstraint(
            "status IN ('observed', 'missed', 'not_observable_before_tracking')",
            name="ck_forward_outcome_status",
        ),
        sa.CheckConstraint(
            "(status = 'observed') = (observed_at IS NOT NULL)",
            name="ck_forward_outcome_observed_time",
        ),
    )


def downgrade() -> None:
    op.drop_table("forward_outcome_observations")
