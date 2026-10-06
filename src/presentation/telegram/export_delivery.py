import gzip

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import BufferedInputFile, InputMediaDocument, Message

from application.dto.export import CachedExport
from application.dto.report import DailyQuestionReport
from application.errors import CachedFileUnavailable, ExportTooLarge, RecipientUnavailable
from domain.entities.daily_conversation_export import DailyConversationExport
from domain.value_objects.day_range import DayRange
from presentation.telegram import texts
from presentation.telegram.formatters.export_json import render_export_json
from presentation.telegram.formatters.report_html import render_report_html

# Bot API принимает документы до 50 МБ; берём с запасом на multipart
MAX_UPLOAD_BYTES = 49 * 1024 * 1024
# крупнее — отправляем сжатым
COMPRESS_FROM_BYTES = 20 * 1024 * 1024


class AiogramExportDelivery:
    """Отправляет выгрузку в личный чат с ботом: JSON и HTML-отчёт одним альбомом."""

    def __init__(
        self,
        bot: Bot,
        *,
        max_upload_bytes: int = MAX_UPLOAD_BYTES,
        compress_from_bytes: int = COMPRESS_FROM_BYTES,
    ) -> None:
        self._bot = bot
        self._max_upload_bytes = max_upload_bytes
        self._compress_from_bytes = compress_from_bytes

    async def send(
        self, user_id: int, export: DailyConversationExport, report: DailyQuestionReport | None
    ) -> list[str]:
        files = [self.prepare_file(export)]
        if report is not None:
            files.append(self.prepare_report(export, report))
        caption = texts.export_caption(
            export.day.day, export.conversations_count, export.messages_count
        )
        messages = await self._send_files(
            user_id, [BufferedInputFile(content, filename=name) for content, name in files], caption
        )
        return [message.document.file_id for message in messages]

    async def resend(self, user_id: int, day: DayRange, cached: CachedExport) -> None:
        caption = texts.export_caption(day.day, cached.conversations_count, cached.messages_count)
        try:
            await self._send_files(user_id, list(cached.file_ids), caption)
        except TelegramBadRequest as exc:
            # file_id устарел (например, сменился токен бота) — выгрузим заново
            raise CachedFileUnavailable() from exc

    async def _send_files(
        self, user_id: int, files: list[BufferedInputFile | str], caption: str
    ) -> list[Message]:
        try:
            if len(files) == 1:
                return [await self._bot.send_document(user_id, files[0], caption=caption)]
            # подпись у альбома показывается под последним файлом
            media = [InputMediaDocument(media=file) for file in files[:-1]]
            media.append(InputMediaDocument(media=files[-1], caption=caption))
            return await self._bot.send_media_group(user_id, media)
        except TelegramForbiddenError as exc:
            raise RecipientUnavailable() from exc

    def prepare_report(
        self, export: DailyConversationExport, report: DailyQuestionReport
    ) -> tuple[bytes, str]:
        content = render_report_html(report)
        if len(content) > self._max_upload_bytes:
            raise ExportTooLarge()
        return content, f"support_{export.day.day.isoformat()}_report.html"

    def prepare_file(self, export: DailyConversationExport) -> tuple[bytes, str]:
        content = render_export_json(export)
        filename = f"support_{export.day.day.isoformat()}.json"
        if len(content) >= self._compress_from_bytes:
            content, filename = gzip.compress(content), filename + ".gz"
        if len(content) > self._max_upload_bytes:
            raise ExportTooLarge()
        return content, filename

