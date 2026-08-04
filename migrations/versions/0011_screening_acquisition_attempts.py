"""Create screening_acquisition_attempts -- durable, append-only provider
acquisition attempt records (SPRINT-013 S13-02).

Additive only, mirrors 0006/0010's own conventions: an auto-incrementing
surrogate key (this table accumulates one row per provider attempt, not one
row per pair), indexes on every column S13-02's acceptance requires
queryable (cycle, pair, provider, capability, outcome, time), and a unique
constraint on (pair_evaluation_id, sequence) -- the idempotency key
AcquisitionAttemptRepository implementations rely on so re-recording the
same attempt (e.g. a caller-level retry of the persistence write itself,
not a new provider attempt) is a no-op rather than a duplicate row.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "screening_acquisition_attempts"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("screening_cycle_id", sa.String(length=96), nullable=False),
        sa.Column("pair_evaluation_id", sa.String(length=255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("fulfillment_status", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("diagnostic_code", sa.String(length=64), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("safe_summary", sa.String(length=500), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "pair_evaluation_id", "sequence", name="uq_screening_acquisition_attempts_pair_sequence"
        ),
    )
    op.create_index(
        "ix_screening_acquisition_attempts_cycle", _TABLE, ["screening_cycle_id"]
    )
    op.create_index(
        "ix_screening_acquisition_attempts_pair", _TABLE, ["pair_evaluation_id"]
    )
    op.create_index(
        "ix_screening_acquisition_attempts_provider", _TABLE, ["provider_id"]
    )
    op.create_index(
        "ix_screening_acquisition_attempts_capability", _TABLE, ["capability"]
    )
    op.create_index(
        "ix_screening_acquisition_attempts_outcome", _TABLE, ["outcome"]
    )
    op.create_index(
        "ix_screening_acquisition_attempts_recorded_at", _TABLE, ["recorded_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_screening_acquisition_attempts_recorded_at", table_name=_TABLE)
    op.drop_index("ix_screening_acquisition_attempts_outcome", table_name=_TABLE)
    op.drop_index("ix_screening_acquisition_attempts_capability", table_name=_TABLE)
    op.drop_index("ix_screening_acquisition_attempts_provider", table_name=_TABLE)
    op.drop_index("ix_screening_acquisition_attempts_pair", table_name=_TABLE)
    op.drop_index("ix_screening_acquisition_attempts_cycle", table_name=_TABLE)
    op.drop_table(_TABLE)
