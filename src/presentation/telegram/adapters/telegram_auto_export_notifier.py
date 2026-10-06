"""Уведомления владельцу в Telegram о результате автовыгрузки."""
import logging
from datetime import date

from aiogram import Bot

from application.dto.export_summary import ExportSummary
from application.user_facing_errors import ApplicationError
from domain.business_rule_errors import DomainError
from presentation.telegram import bot_texts
from presentation.telegram.keyboards import menu_keyboards

logger = logging.getLogger(__name__)


class AiogramAutoExportNotifier:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def completed(self, user_id: int, summary: ExportSummary) -> None:
        await self._send(
            user_id, bot_texts.auto_export_completed_note(summary.day.day, summary.messages_count)
        )

    async def failed(self, user_id: int, day: date, error: ApplicationError | DomainError) -> None:
        reason = bot_texts.error_text(error) or bot_texts.UNEXPECTED_ERROR
        await self._send(user_id, bot_texts.auto_export_failed(day, reason))

    async def _send(self, user_id: int, text: str) -> None:
        try:
            await self._bot.send_message(user_id, text, reply_markup=menu_keyboards.back_to_main())
        except Exception:
            # уведомление не критично: о блокировке бота узнаем при отправке файла
            logger.warning("Auto export notification not delivered: user=%s", user_id, exc_info=True)
