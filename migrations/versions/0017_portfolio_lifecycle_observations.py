"""Add append-only lifecycle observations and evidence time.

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tracked_candidates",
        sa.Column("evidence_observed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE tracked_candidates SET evidence_observed_at = originating_observed_at")
    op.alter_column("tracked_candidates", "evidence_observed_at", nullable=False)
    op.create_table(
        "portfolio_lifecycle_observations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "tracked_candidate_id",
            sa.Uuid(),
            sa.ForeignKey("tracked_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("broker_position_key", sa.String(512), nullable=True),
        sa.Column("broker_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("strategy_result_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('tracked', 'open', 'closed')",
            name="ck_portfolio_lifecycle_observation_state",
        ),
        sa.UniqueConstraint(
            "tracked_candidate_id",
            "broker_observed_at",
            name="uq_portfolio_lifecycle_candidate_broker_time",
        ),
    )


def downgrade() -> None:
    op.drop_table("portfolio_lifecycle_observations")
    op.drop_column("tracked_candidates", "evidence_observed_at")
