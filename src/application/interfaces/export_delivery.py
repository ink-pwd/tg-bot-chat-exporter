from typing import Protocol

from application.dto.export import CachedExport
from application.dto.report import DailyQuestionReport
from domain.entities.daily_conversation_export import DailyConversationExport
from domain.entities.telegram_account import TelegramAccount
from domain.value_objects.day_range import DayRange


class ExportDelivery(Protocol):
    """Доставка файла выгрузки пользователю."""

    async def send(
        self, user_id: int, export: DailyConversationExport, report: DailyQuestionReport | None
    ) -> list[str]:
        """Отправляет JSON и отчёт (если есть) одним альбомом; возвращает file_id файлов.

        Raises:
            ExportTooLarge: файл не помещается в лимит.
            RecipientUnavailable: пользователь заблокировал бота.
        """
        ...

    async def resend(
        self, user_id: int, account: TelegramAccount, day: DayRange, cached: CachedExport
    ) -> None:
        """Raises: CachedFileUnavailable, RecipientUnavailable."""
        ...
