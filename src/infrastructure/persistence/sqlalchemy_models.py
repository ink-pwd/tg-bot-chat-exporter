"""Таблицы базы данных (модели SQLAlchemy): пользователи, беседы, сообщения, расписания."""
from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BotUserModel(Base):
    __tablename__ = "bot_users"

    # id пользователя Telegram, которого прислал Bot API
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    # IANA-имя; NULL — пояс по умолчанию из настроек
    timezone: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SupportChatModel(Base):
    __tablename__ = "support_chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # меняется, когда группа становится супергруппой
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bot_users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    chat_type: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean)
    # JSON-массив id админов; NULL — список ещё не получали
    admin_ids: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ChatMessageModel(Base):
    """Текст, имя отправителя и источник пересылки хранятся только в зашифрованном виде."""

    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_support_chat_sent", "support_chat_id", "sent_at"),)

    # Telegram id беседы на момент отправки: id сообщений уникальны только внутри неё
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    support_chat_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("support_chats.id", ondelete="CASCADE")
    )
    sender_id: Mapped[int | None] = mapped_column(BigInteger)
    sent_at: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC
    edited_at: Mapped[datetime | None] = mapped_column(DateTime)  # UTC
    reply_to_id: Mapped[int | None] = mapped_column(BigInteger)
    media_type: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str | None] = mapped_column(String(64))
    encrypted_content: Mapped[bytes] = mapped_column(LargeBinary)


class ExportScheduleModel(Base):
    __tablename__ = "export_schedules"

    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bot_users.id", ondelete="CASCADE"), primary_key=True
    )
    local_time: Mapped[time] = mapped_column(Time)
    enabled: Mapped[bool] = mapped_column(Boolean, index=True)
    last_run_day: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
