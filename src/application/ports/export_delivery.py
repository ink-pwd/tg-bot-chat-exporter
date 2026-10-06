"""Как результат выгрузки доходит до пользователя. Реализации — в presentation/telegram/adapters."""
from datetime import date
from enum import IntEnum
from typing import Protocol

from application.dto.daily_report import DailyQuestionReport
from application.dto.export_summary import CachedExport, ExportSummary
from application.user_facing_errors import ApplicationError
from domain.business_rule_errors import DomainError
from domain.entities.daily_conversation_export import DailyConversationExport
from domain.value_objects.day_range import DayRange


class ExportDelivery(Protocol):
    """Доставка файла выгрузки пользователю в личный чат с ботом."""

    async def send(
        self, user_id: int, export: DailyConversationExport, report: DailyQuestionReport | None
    ) -> list[str]:
        """Отправляет JSON и отчёт (если есть) одним альбомом; возвращает file_id файлов.

        Raises:
            ExportTooLarge: файл не помещается в лимит.
            RecipientUnavailable: пользователь заблокировал бота.
        """
        ...

    async def resend(self, user_id: int, day: DayRange, cached: CachedExport) -> None:
        """Raises: CachedFileUnavailable, RecipientUnavailable."""
        ...


class AutoExportNotifier(Protocol):
    """Сообщения владельцу о ночной автовыгрузке. Ошибки отправки не пробрасываются."""

    async def completed(self, user_id: int, summary: ExportSummary) -> None: ...

    async def failed(self, user_id: int, day: date, error: ApplicationError | DomainError) -> None: ...


class ExportStage(IntEnum):
    """Этапы выгрузки по порядку — по ним пользователь видит, сколько осталось."""

    COLLECTING = 1  # сообщения бесед за день из базы и админы бесед из Telegram
    ANALYZING = 2  # обращения, типы запросов, время ответа
    SENDING = 3  # JSON и HTML-отчёт формируются и отправляются


class ExportProgress(Protocol):
    async def stage(self, stage: ExportStage) -> None:
        """Сообщает о начале этапа. Ошибки показа прогресса не должны ломать выгрузку."""
        ...
