"""Доступ к боту: личка — только для ALLOWED_USER_IDS, события из групп пропускаются."""
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import Chat, TelegramObject, User

logger = logging.getLogger(__name__)

GROUP_CHATS = {ChatType.GROUP, ChatType.SUPERGROUP}


class AccessMiddleware(BaseMiddleware):
    """Личный чат с ботом — только для пользователей из ALLOWED_USER_IDS (если список задан).

    События из групп пропускаются: там пишут клиенты, которых в списке нет.
    Кто может подключить беседу, проверяет обработчик добавления бота через allows().
    Каналы и прочие чаты игнорируются.
    """

    def __init__(self, allowed_user_ids: frozenset[int]) -> None:
        self._allowed = allowed_user_ids

    def allows(self, user_id: int) -> bool:
        return not self._allowed or user_id in self._allowed

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        chat: Chat | None = data.get("event_chat")
        if chat is not None and chat.type in GROUP_CHATS:
            return await handler(event, data)
        if user is None or (chat is not None and chat.type != ChatType.PRIVATE):
            return None
        if not self.allows(user.id):
            logger.info("Access denied: user=%s", user.id)
            return None
        return await handler(event, data)
