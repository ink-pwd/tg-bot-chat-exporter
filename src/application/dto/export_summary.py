"""Итог выгрузки для пользователя и запись кеша об уже отправленных файлах."""
from dataclasses import dataclass
from datetime import datetime

from domain.value_objects.day_range import DayRange


@dataclass(frozen=True)
class CachedExport:
    """Ссылка на уже отправленную выгрузку. Текстов сообщений здесь нет."""

    file_ids: tuple[str, ...]  # JSON и HTML-отчёт
    conversations_count: int
    messages_count: int
    exported_at: datetime


@dataclass(frozen=True)
class ExportSummary:
    day: DayRange
    conversations_count: int
    messages_count: int
    exported_at: datetime
    from_cache: bool
