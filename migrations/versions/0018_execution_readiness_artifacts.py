"""Persist latest execution readiness and immutable tracked attachments.

Revision ID: 0018
Revises: 0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_readiness_artifacts",
        sa.Column("originating_observation_id", sa.String(128), nullable=False),
        sa.Column("signal_id", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("assessment_identity", sa.String(64), nullable=False),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("assessment_json", sa.Text(), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("signal_id", "symbol"),
    )
    op.add_column(
        "tracked_candidates",
        sa.Column("resolved_proposal_identity", sa.String(64), nullable=True),
    )
    op.add_column(
        "tracked_candidates",
        sa.Column("resolved_proposal_json", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_tracked_candidate_resolved_proposal_pair",
        "tracked_candidates",
        "(resolved_proposal_identity IS NULL) = (resolved_proposal_json IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_tracked_candidate_resolved_proposal_pair",
        "tracked_candidates",
        type_="check",
    )
    op.drop_column("tracked_candidates", "resolved_proposal_json")
    op.drop_column("tracked_candidates", "resolved_proposal_identity")
    op.drop_table("execution_readiness_artifacts")
