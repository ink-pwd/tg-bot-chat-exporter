"""user timezones and export schedules

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bot_users", sa.Column("timezone", sa.String(64), nullable=True))
    op.create_table(
        "export_schedules",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("local_time", sa.Time(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_run_day", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["telegram_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )
    op.create_index("ix_export_schedules_enabled", "export_schedules", ["enabled"])


def downgrade() -> None:
    op.drop_table("export_schedules")
    op.drop_column("bot_users", "timezone")
