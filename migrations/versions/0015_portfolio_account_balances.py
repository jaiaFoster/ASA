"""Add authoritative optional broker account balances.

Revision ID: 0015
Revises: 0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in (
        "cash_balance",
        "cash_available_for_withdrawal",
        "buying_power",
        "account_value",
    ):
        op.add_column(
            "broker_accounts",
            sa.Column(name, sa.Numeric(precision=24, scale=8), nullable=True),
        )


def downgrade() -> None:
    for name in (
        "account_value",
        "buying_power",
        "cash_available_for_withdrawal",
        "cash_balance",
    ):
        op.drop_column("broker_accounts", name)
