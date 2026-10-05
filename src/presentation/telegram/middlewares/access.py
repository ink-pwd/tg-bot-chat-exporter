import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import Chat, TelegramObject, User

logger = logging.getLogger(__name__)


class AccessMiddleware(BaseMiddleware):
    """Только личные чаты и только пользователи из ALLOWED_USER_IDS (если список задан)."""

    def __init__(self, allowed_user_ids: frozenset[int]) -> None:
        self._allowed = allowed_user_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        chat: Chat | None = data.get("event_chat")
        if user is None or (chat is not None and chat.type != ChatType.PRIVATE):
            return None
        if self._allowed and user.id not in self._allowed:
            logger.info("Access denied: user=%s", user.id)
            return None
        return await handler(event, data)
