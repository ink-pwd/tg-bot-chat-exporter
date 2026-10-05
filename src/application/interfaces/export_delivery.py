from typing import Protocol

from application.dto.export import CachedExport
from domain.entities.daily_conversation_export import DailyConversationExport
from domain.entities.telegram_account import TelegramAccount
from domain.value_objects.day_range import DayRange


class ExportDelivery(Protocol):
    """Доставка файла выгрузки пользователю."""

    async def send(self, user_id: int, export: DailyConversationExport) -> str:
        """Отправляет файл и возвращает ссылку для повторной отправки (file_id).

        Raises:
            ExportTooLarge: файл не помещается в лимит.
        """
        ...

    async def resend(
        self, user_id: int, account: TelegramAccount, day: DayRange, cached: CachedExport
    ) -> None:
        """Raises: CachedFileUnavailable."""
        ...
