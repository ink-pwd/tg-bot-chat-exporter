import contextlib
from datetime import date

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from application.use_cases.export_daily_conversations import ExportDailyConversations
from presentation.telegram import texts
from presentation.telegram.callbacks import ExportCallback
from presentation.telegram.export_progress import MessageExportProgress
from presentation.telegram.handlers.common import edit_or_answer
from presentation.telegram.keyboards import menus

router = Router(name="export")


@router.callback_query(ExportCallback.filter(F.action == "days"))
async def choose_day(callback: CallbackQuery, export: ExportDailyConversations) -> None:
    # дни считаются в момент нажатия: после полуночи список сдвигается сам
    days = await export.available_days(callback.from_user.id)
    labels = [texts.day_button(day, days[0]) for day in days]
    await callback.answer()
    await edit_or_answer(callback, texts.CHOOSE_DAY, menus.export_days(days, labels))


@router.callback_query(ExportCallback.filter(F.action.in_({"day", "refresh"})))
async def export_day(
    callback: CallbackQuery, callback_data: ExportCallback, export: ExportDailyConversations
) -> None:
    try:
        day = date.fromisoformat(callback_data.day)
    except ValueError:  # callback_data можно подделать
        await callback.answer(texts.UNEXPECTED_ERROR, show_alert=True)
        return
    # выгрузка может занять время, а callback нужно подтвердить сразу
    await callback.answer()
    await _run_export(
        callback.message,
        export,
        callback.from_user.id,
        day,
        refresh=callback_data.action == "refresh",
    )


async def _run_export(
    chat_message: Message,
    export: ExportDailyConversations,
    user_id: int,
    day: date,
    *,
    refresh: bool,
) -> None:
    status = await chat_message.answer(texts.export_progress(day, None))
    try:
        summary = await export.execute(
            user_id, day, refresh=refresh, progress=MessageExportProgress(status, day)
        )
    finally:
        with contextlib.suppress(TelegramBadRequest):
            await status.delete()
    await chat_message.answer(
        texts.export_summary(
            day,
            summary.conversations_count,
            summary.messages_count,
            summary.exported_at,
            summary.from_cache,
            summary.day.timezone,
        ),
        reply_markup=menus.export_done(day, can_refresh=day == await export.today(user_id)),
    )
