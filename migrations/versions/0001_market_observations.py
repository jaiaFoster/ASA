"""Create canonical market observations.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_observations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("price", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("selected_provider", sa.String(length=64), nullable=False),
        sa.Column("original_provider", sa.String(length=64), nullable=False),
        sa.Column("cache_status", sa.String(length=32), nullable=False),
        sa.Column("freshness_status", sa.String(length=32), nullable=False),
        sa.Column("fallback_reason", sa.Text(), nullable=True),
        sa.Column("provider_request_id", sa.String(length=128), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_market_observations_price_nonnegative"),
    )
    op.create_index(
        "ix_market_observations_symbol_observed_at",
        "market_observations",
        ["symbol", sa.text("observed_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_market_observations_symbol_observed_at", table_name="market_observations")
    op.drop_table("market_observations")
