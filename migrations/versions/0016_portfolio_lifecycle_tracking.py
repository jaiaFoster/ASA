"""Create tracked candidates and append-only position associations.

Revision ID: 0016
Revises: 0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tracked_candidates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("originating_observation_id", sa.String(128), nullable=False, unique=True),
        sa.Column("opportunity_id", sa.String(128), nullable=True),
        sa.Column("signal_id", sa.String(64), nullable=False),
        sa.Column("signal_version", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("tracked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("originating_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exact_option_symbols", sa.JSON(), nullable=False),
    )
    op.create_table(
        "portfolio_position_associations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "tracked_candidate_id",
            sa.Uuid(),
            sa.ForeignKey("tracked_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("broker_position_key", sa.String(512), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tracked_candidate_id", "broker_position_key", "state", "observed_at",
            name="uq_portfolio_position_association_observation",
        ),
        sa.CheckConstraint(
            "state IN ('tracked', 'matched', 'ambiguous', 'no_match')",
            name="ck_portfolio_position_association_state",
        ),
    )


def downgrade() -> None:
    op.drop_table("portfolio_position_associations")
    op.drop_table("tracked_candidates")
