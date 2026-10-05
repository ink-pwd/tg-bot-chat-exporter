from dataclasses import dataclass
from datetime import datetime

from domain.entities.conversation import Conversation
from domain.entities.telegram_account import TelegramAccount
from domain.value_objects.day_range import DayRange
from domain.value_objects.telegram_profile import TelegramProfile


@dataclass(frozen=True)
class FetchedDay:
    """Что шлюз достал из Telegram за день."""

    profile: TelegramProfile
    phone: str | None
    conversations: list[Conversation]


@dataclass(frozen=True)
class CachedExport:
    """Ссылка на уже отправленную выгрузку. Текстов сообщений здесь нет."""

    file_ids: tuple[str, ...]  # JSON и HTML-отчёт; пусто — за день не было сообщений
    conversations_count: int
    messages_count: int
    exported_at: datetime


@dataclass(frozen=True)
class ExportSummary:
    account: TelegramAccount
    day: DayRange
    conversations_count: int
    messages_count: int
    exported_at: datetime
    from_cache: bool
