"""Действия бота в беседе. Реализация — в infrastructure/telegram/bot."""
from typing import Protocol


class TelegramChatGateway(Protocol):
    """Действия бота в беседе. Ошибки Telegram переводятся в application.user_facing_errors."""

    async def get_admin_ids(self, telegram_chat_id: int) -> frozenset[int]:
        """Raises: TelegramUnavailable — бота нет в беседе или Telegram недоступен."""
        ...

    async def leave(self, telegram_chat_id: int) -> None:
        """Выходит из беседы; если бота там уже нет, ничего не делает."""
        ...
