"""initial schema: bot users, support chats, chat messages, export schedules

Revision ID: 0001
Revises:
Create Date: 2026-10-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_users",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "support_chats",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("chat_type", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("admin_ids", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["bot_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_chat_id"),
    )
    op.create_index("ix_support_chats_owner_id", "support_chats", ["owner_id"])

    op.create_table(
        "chat_messages",
        sa.Column("telegram_chat_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("message_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("support_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_id", sa.BigInteger(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column("reply_to_id", sa.BigInteger(), nullable=True),
        sa.Column("media_type", sa.String(32), nullable=True),
        sa.Column("action", sa.String(64), nullable=True),
        sa.Column("encrypted_content", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(["support_chat_id"], ["support_chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("telegram_chat_id", "message_id"),
    )
    op.create_index(
        "ix_chat_messages_support_chat_sent", "chat_messages", ["support_chat_id", "sent_at"]
    )
    op.create_index("ix_chat_messages_sent_at", "chat_messages", ["sent_at"])

    op.create_table(
        "export_schedules",
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("local_time", sa.Time(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_run_day", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["bot_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("owner_id"),
    )
    op.create_index("ix_export_schedules_enabled", "export_schedules", ["enabled"])


def downgrade() -> None:
    op.drop_table("export_schedules")
    op.drop_table("chat_messages")
    op.drop_table("support_chats")
    op.drop_table("bot_users")
