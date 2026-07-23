"""Create opportunity_observation_history -- append-only observation
history for lifecycle-tracked strategy_runtime opportunities (SPRINT-009R/
EPIC-R3).

Additive only, mirrors 0005's own naming rationale: no primary key on
(opportunity_id) alone since this table accumulates one row per
observation, not one row per opportunity -- an auto-incrementing surrogate
key plus an index on opportunity_id (every read strategy_runtime.
persistence.ObservationHistoryRepository.history_for() needs) instead.
Column names avoid "strategy" for the same asa/ boundary reason 0004/0005
already established (tests/asa/test_boundaries.py::
test_forbidden_legacy_technologies_are_absent).

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_observation_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("opportunity_id", sa.String(length=128), nullable=False),
        sa.Column("signal_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("lifecycle_stage", sa.String(length=64), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_opportunity_observation_history_opportunity_id",
        "opportunity_observation_history",
        ["opportunity_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_opportunity_observation_history_opportunity_id",
        table_name="opportunity_observation_history",
    )
    op.drop_table("opportunity_observation_history")
