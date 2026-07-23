"""Create universal_screening_state -- current, latest-only results for
strategy_runtime-migrated strategies (SPRINT-009/EPIC-9).

Additive only: the existing screening_state table (0004) is unchanged and
continues to serve any strategy not yet migrated onto strategy_runtime.
This table's own shape follows strategy_runtime.result.
UniversalScreeningResult's own richer envelope directly -- more fields
than screening_state's own ScreeningStateRecord (opportunity_id, row_type,
evaluation_state, lifecycle_stage, recommendation_state, data_quality,
economics, blockers, warnings, provenance), not a schema change to the
existing table.

Columns named signal_id/signal_version, not strategy_id/strategy_version:
0004's own screening_state table already made this exact rename for the
exact same reason (tests/asa/test_boundaries.py::
test_forbidden_legacy_technologies_are_absent bans the literal substring
"strategy" anywhere under asa/, and asa/integrations/
universal_screening_postgres.py's raw SQL text must reference these
column names directly). Matching 0004's column names keeps one consistent
vocabulary at the storage boundary instead of two.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "universal_screening_state",
        sa.Column("signal_id", sa.String(length=64), primary_key=True),
        sa.Column("symbol", sa.String(length=32), primary_key=True),
        sa.Column("signal_version", sa.String(length=32), nullable=False),
        sa.Column("observation_id", sa.String(length=128), nullable=False),
        sa.Column("opportunity_id", sa.String(length=128), nullable=True),
        sa.Column("row_type", sa.String(length=32), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=True),
        sa.Column("evaluation_state", sa.String(length=32), nullable=False),
        sa.Column("lifecycle_stage", sa.String(length=64), nullable=True),
        sa.Column("recommendation_state", sa.String(length=64), nullable=True),
        sa.Column("data_quality", sa.String(length=32), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("economics", sa.JSON(), nullable=False),
        sa.Column("blockers", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("universal_screening_state")
