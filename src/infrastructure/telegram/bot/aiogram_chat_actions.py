"""Действия бота в беседе через Bot API: список администраторов и выход из беседы."""
import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

from application.user_facing_errors import TelegramUnavailable, TooManyAttempts

logger = logging.getLogger(__name__)


class AiogramChatGateway:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def get_admin_ids(self, telegram_chat_id: int) -> frozenset[int]:
        try:
            admins = await self._bot.get_chat_administrators(telegram_chat_id)
        except TelegramRetryAfter as exc:
            raise TooManyAttempts(exc.retry_after) from exc
        except Exception as exc:
            logger.warning("Chat admins request failed: %s", type(exc).__name__)
            raise TelegramUnavailable() from exc
        return frozenset(member.user.id for member in admins if not member.user.is_bot)

    async def leave(self, telegram_chat_id: int) -> None:
        try:
            await self._bot.leave_chat(telegram_chat_id)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass  # бота в беседе уже нет
        except Exception as exc:
            logger.warning("Leave chat failed: %s", type(exc).__name__)
            raise TelegramUnavailable() from exc
