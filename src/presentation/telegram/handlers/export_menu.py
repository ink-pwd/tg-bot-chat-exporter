"""Меню выгрузки: выбор дня из последних 7 и запуск выгрузки со шкалой загрузки."""
import contextlib
from datetime import date

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from application.use_cases.export_daily_conversations import ExportDailyConversations
from presentation.telegram import bot_texts
from presentation.telegram.adapters.telegram_export_progress import MessageExportProgress
from presentation.telegram.callback_data import ExportCallback
from presentation.telegram.handlers.main_menu_and_errors import edit_or_answer
from presentation.telegram.keyboards import menu_keyboards

router = Router(name="export_menu")


@router.callback_query(ExportCallback.filter(F.action == "days"))
async def choose_day(callback: CallbackQuery, export: ExportDailyConversations) -> None:
    # дни считаются в момент нажатия: после полуночи список сдвигается сам
    days = await export.available_days(callback.from_user.id)
    labels = [bot_texts.day_button(day, days[0]) for day in days]
    await callback.answer()
    await edit_or_answer(callback, bot_texts.CHOOSE_DAY, menu_keyboards.export_days(days, labels))


@router.callback_query(ExportCallback.filter(F.action.in_({"day", "refresh"})))
async def export_day(
    callback: CallbackQuery, callback_data: ExportCallback, export: ExportDailyConversations
) -> None:
    try:
        day = date.fromisoformat(callback_data.day)
    except ValueError:  # callback_data можно подделать
        await callback.answer(bot_texts.UNEXPECTED_ERROR, show_alert=True)
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
    status = await chat_message.answer(bot_texts.export_progress(day, None))
    try:
        summary = await export.execute(
            user_id, day, refresh=refresh, progress=MessageExportProgress(status, day)
        )
    finally:
        with contextlib.suppress(TelegramBadRequest):
            await status.delete()
    await chat_message.answer(
        bot_texts.export_summary(
            day,
            summary.conversations_count,
            summary.messages_count,
            summary.exported_at,
            summary.from_cache,
            summary.day.timezone,
        ),
        reply_markup=menu_keyboards.export_done(day, can_refresh=day == await export.today(user_id)),
    )
