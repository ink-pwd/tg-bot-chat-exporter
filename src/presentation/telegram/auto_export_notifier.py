import logging
from datetime import date

from aiogram import Bot

from application.dto.export import ExportSummary
from application.errors import ApplicationError
from domain.entities.telegram_account import TelegramAccount
from domain.errors import DomainError
from presentation.telegram import texts
from presentation.telegram.keyboards import menus

logger = logging.getLogger(__name__)


class AiogramAutoExportNotifier:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def completed(self, user_id: int, summary: ExportSummary) -> None:
        await self._send(
            user_id, texts.auto_export_completed_note(summary.day.day, summary.messages_count)
        )

    async def account_revoked(self, user_id: int, account: TelegramAccount) -> None:
        await self._send(user_id, texts.auto_export_revoked(account))

    async def failed(
        self, user_id: int, account: TelegramAccount, day: date, error: ApplicationError | DomainError
    ) -> None:
        reason = texts.error_text(error) or texts.UNEXPECTED_ERROR
        await self._send(user_id, texts.auto_export_failed(account, day, reason))

    async def _send(self, user_id: int, text: str) -> None:
        try:
            await self._bot.send_message(user_id, text, reply_markup=menus.main_menu())
        except Exception:
            # уведомление не критично: о блокировке бота узнаем при отправке файла
            logger.warning("Auto export notification not delivered: user=%s", user_id, exc_info=True)
