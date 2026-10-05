"""Фейки для сценария выгрузки."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from application.dto.export import CachedExport, FetchedDay
from application.errors import CachedFileUnavailable
from domain.entities.conversation import Conversation
from domain.entities.daily_conversation_export import DailyConversationExport
from domain.entities.support_message import SupportMessage
from domain.entities.telegram_account import TelegramAccount
from domain.enums.chat_type import ChatType
from domain.value_objects.day_range import DayRange
from domain.value_objects.telegram_profile import TelegramProfile
from domain.value_objects.telegram_session import TelegramSession


def message(id: int, sent_at: datetime, text: str = "Как изменить способ оплаты?") -> SupportMessage:
    return SupportMessage(
        id=id,
        chat_id=10,
        sender_id=1,
        sender_name="Клиент",
        text=text,
        sent_at=sent_at,
        edited_at=None,
        is_outgoing=False,
        reply_to_id=None,
        forwarded_from=None,
        media_type=None,
        action=None,
    )


def conversation(*messages: SupportMessage) -> Conversation:
    return Conversation(chat_id=10, title="Клиент", chat_type=ChatType.PRIVATE, messages=list(messages))


@dataclass
class FakeMessageGateway:
    conversations: list[Conversation] = field(default_factory=list)
    error: Exception | None = None
    calls: list[tuple[TelegramSession, DayRange]] = field(default_factory=list)
    delay: float = 0

    async def fetch_day(self, session: TelegramSession, day: DayRange) -> FetchedDay:
        self.calls.append((session, day))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return FetchedDay(TelegramProfile(555, "Support", "support"), "380501234567", self.conversations)


@dataclass
class InMemoryExportCache:
    rows: dict[tuple[int, str, str], CachedExport] = field(default_factory=dict)
    ttls: dict[tuple[int, str, str], timedelta] = field(default_factory=dict)
    reads: list[int] = field(default_factory=list)

    async def get(self, account_id: int, day: DayRange) -> CachedExport | None:
        self.reads.append(account_id)
        return self.rows.get(_key(account_id, day))

    async def put(self, account_id: int, day: DayRange, export: CachedExport, ttl: timedelta) -> None:
        self.rows[_key(account_id, day)] = export
        self.ttls[_key(account_id, day)] = ttl

    async def delete(self, account_id: int, day: DayRange) -> None:
        self.rows.pop(_key(account_id, day), None)


def _key(account_id: int, day: DayRange) -> tuple[int, str, str]:
    return account_id, day.day.isoformat(), day.timezone.key


@dataclass
class FakeDelivery:
    sent: list[tuple[int, DailyConversationExport]] = field(default_factory=list)
    resent: list[tuple[int, str]] = field(default_factory=list)
    stale_file_ids: set[str] = field(default_factory=set)

    async def send(self, user_id: int, export: DailyConversationExport) -> str:
        self.sent.append((user_id, export))
        return f"file-{len(self.sent)}"

    async def resend(
        self, user_id: int, account: TelegramAccount, day: DayRange, cached: CachedExport
    ) -> None:
        if cached.file_id in self.stale_file_ids:
            raise CachedFileUnavailable()
        self.resent.append((user_id, cached.file_id))
