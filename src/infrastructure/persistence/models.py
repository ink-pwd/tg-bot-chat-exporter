from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
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


class TelegramAccountModel(Base):
    __tablename__ = "telegram_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bot_users.id", ondelete="CASCADE"), index=True
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TelegramSessionModel(Base):
    __tablename__ = "telegram_sessions"

    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("telegram_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    encrypted_session: Mapped[bytes] = mapped_column(LargeBinary)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ExportScheduleModel(Base):
    __tablename__ = "export_schedules"

    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("telegram_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    local_time: Mapped[time] = mapped_column(Time)
    enabled: Mapped[bool] = mapped_column(Boolean, index=True)
    last_run_day: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
