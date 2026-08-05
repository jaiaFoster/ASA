"""Create historical_skew_observations -- durable, provider-neutral
canonical historical skew evidence (SPRINT-013 S13-04B).

Additive only: no existing table is touched. A dedicated table, deliberately
separate from opportunity_observation_history (0006) -- that table is
strategy-verdict lifecycle history (lifecycle_stage/verdict/
recommended_action), this one is canonical market-fact history
(call_skew/put_skew/evidence), a different ownership layer entirely
(this ticket's own "do not mix canonical observations and derived
analytics/strategy-verdict history in one ownership layer" rule).

Canonical uniqueness is (instrument_scheme, instrument_value,
trading_session_date) -- one row per instrument per trading session,
never per raw timestamp (S13-04A.1's own correction of the original
identity). effective_time is stored separately from trading_session_date:
it is always that session's own canonical close time
(strategy_runtime.historical_evidence.record_prospective_skew_observation()
canonicalizes it before any row is ever written), kept as its own column
because callers query and reason about it as a timestamp, not a date.

schema_version is an explicit column on this table, not a change to
domain.strategy_evidence.HistoricalSkewObservation itself (that SPRINT-012
domain type is deliberately left unchanged -- see project/reports/
SPRINT-013-S13-04-trace.md and PR #274's own scope note). This gives a
future normalization revision a traceable persistence-layer boundary
without silently reinterpreting already-recorded sessions under a new
meaning, per explicit Founder direction on this PR.

One composite primary key index on (instrument_scheme, instrument_value,
trading_session_date) is the only index this table needs: every query
shape this ticket requires -- lookup by instrument, a session-date range
for one instrument, the bounded "latest N sessions" query, and an as-of
query -- filters and orders by exactly this same leading column set, and
a B-tree index supports range scans and ORDER BY ... DESC LIMIT N equally
well in either direction. No separate index was added merely to have one;
that would duplicate what the primary key already provides.

No retention or deletion policy -- explicitly out of this ticket's scope,
per its own "do not invent retention limits" instruction. Estimated row
growth: one row per instrument per trading session, ~252 sessions/year;
at the current ~30-symbol approved universe, ~7,500 rows/year -- trivial.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "historical_skew_observations",
        sa.Column("instrument_scheme", sa.String(length=32), nullable=False),
        sa.Column("instrument_value", sa.String(length=64), nullable=False),
        sa.Column("trading_session_date", sa.Date(), nullable=False),
        sa.Column("call_skew", sa.Numeric(), nullable=False),
        sa.Column("put_skew", sa.Numeric(), nullable=False),
        sa.Column("effective_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint(
            "instrument_scheme",
            "instrument_value",
            "trading_session_date",
            name="pk_historical_skew_observations",
        ),
    )


def downgrade() -> None:
    op.drop_table("historical_skew_observations")
