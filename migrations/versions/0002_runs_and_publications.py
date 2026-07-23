"""Create persisted runs and atomic publication pointer.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUN_STATUSES = ("requested", "running", "succeeded", "failed")
STEP_STATUSES = ("pending", "running", "succeeded", "failed")
STEP_NAMES = ("acquire_portfolio", "normalize_portfolio", "validate_publication", "publish")


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_sha", sa.String(length=64), nullable=False),
        sa.Column("effective_config_hash", sa.String(length=128), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"status IN {RUN_STATUSES}",
            name="ck_runs_status",
        ),
        sa.CheckConstraint(
            "status <> 'succeeded' OR completed_at IS NOT NULL",
            name="ck_runs_succeeded_completed",
        ),
    )
    op.create_table(
        "run_steps",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_name", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.CheckConstraint(f"step_name IN {STEP_NAMES}", name="ck_run_steps_name"),
        sa.CheckConstraint(f"status IN {STEP_STATUSES}", name="ck_run_steps_status"),
        sa.UniqueConstraint("run_id", "step_name", name="uq_run_steps_run_name"),
    )
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("runs.id"), nullable=False, unique=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_request_id", sa.String(length=128), nullable=False),
    )
    op.create_table(
        "publications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("runs.id"), nullable=False, unique=True),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("portfolio_snapshots.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "publication_pointer",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column(
            "publication_id",
            sa.Uuid(),
            sa.ForeignKey("publications.id"),
            nullable=False,
            unique=True,
        ),
        sa.CheckConstraint("id = 1", name="ck_publication_pointer_singleton"),
    )
    op.execute("""
        CREATE FUNCTION validate_publication_succeeded_run() RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM runs WHERE id = NEW.run_id AND status = 'succeeded'
            ) THEN
                RAISE EXCEPTION 'publication requires a succeeded run';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER publication_succeeded_run
        AFTER INSERT OR UPDATE ON publications
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_publication_succeeded_run()
    """)


def downgrade() -> None:
    op.drop_table("publication_pointer")
    op.execute("DROP TRIGGER publication_succeeded_run ON publications")
    op.execute("DROP FUNCTION validate_publication_succeeded_run")
    op.drop_table("publications")
    op.drop_table("portfolio_snapshots")
    op.drop_table("run_steps")
    op.drop_table("runs")
