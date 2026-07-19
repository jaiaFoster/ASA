"""Create normalized broker accounts and positions.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "broker_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("portfolio_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("connection_id", sa.String(length=128), nullable=False),
        sa.Column("external_account_id", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("account_type", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "snapshot_id",
            "external_account_id",
            name="uq_broker_accounts_snapshot_external",
        ),
    )
    op.create_table(
        "equity_positions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("broker_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("average_cost", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_provider", sa.String(length=64), nullable=False),
    )
    op.create_table(
        "option_legs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("broker_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("underlying_symbol", sa.String(length=16), nullable=False),
        sa.Column("option_symbol", sa.String(length=64), nullable=False),
        sa.Column("option_type", sa.String(length=8), nullable=False),
        sa.Column("strike", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("expiration", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("average_price", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_provider", sa.String(length=64), nullable=False),
        sa.CheckConstraint("option_type IN ('call', 'put')", name="ck_option_legs_type"),
        sa.CheckConstraint("side IN ('long', 'short')", name="ck_option_legs_side"),
    )


def downgrade() -> None:
    op.drop_table("option_legs")
    op.drop_table("equity_positions")
    op.drop_table("broker_accounts")
