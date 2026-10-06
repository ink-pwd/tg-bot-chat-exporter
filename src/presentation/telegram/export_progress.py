import logging
from datetime import date

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from application.interfaces.export_progress import ExportStage
from presentation.telegram import texts

logger = logging.getLogger(__name__)


class MessageExportProgress:
    """Шкала выгрузки в статусном сообщении: бот редактирует его на каждом этапе."""

    def __init__(self, message: Message, day: date) -> None:
        self._message = message
        self._day = day

    async def stage(self, stage: ExportStage) -> None:
        try:
            await self._message.edit_text(texts.export_progress(self._day, stage))
        except TelegramBadRequest:
            pass  # сообщение удалили или текст не изменился — выгрузка продолжается
        except Exception:
            logger.warning("Export progress not shown", exc_info=True)
