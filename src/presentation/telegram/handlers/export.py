import contextlib
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from application.use_cases.export_daily_conversations import ExportDailyConversations
from presentation.telegram import texts
from presentation.telegram.callbacks import ExportCallback
from presentation.telegram.date_input import parse_day
from presentation.telegram.handlers.common import edit_or_answer
from presentation.telegram.keyboards import menus
from presentation.telegram.states import ExportStates

router = Router(name="export")


@router.callback_query(ExportCallback.filter(F.action.in_({"today", "yesterday", "refresh"})))
async def export_day(
    callback: CallbackQuery, callback_data: ExportCallback, export: ExportDailyConversations
) -> None:
    # выгрузка может идти минутами, а callback нужно подтвердить сразу
    await callback.answer()
    today = export.today()
    match callback_data.action:
        case "today":
            day = today
        case "yesterday":
            day = today - timedelta(days=1)
        case _:
            day = date.fromisoformat(callback_data.day)
    await _run_export(
        callback.message,
        export,
        callback.from_user.id,
        callback_data.account_id,
        day,
        refresh=callback_data.action == "refresh",
    )


@router.callback_query(ExportCallback.filter(F.action == "ask_date"))
async def ask_date(
    callback: CallbackQuery,
    callback_data: ExportCallback,
    state: FSMContext,
    export: ExportDailyConversations,
) -> None:
    # владелец проверяется уже здесь, чтобы не спрашивать дату для чужого аккаунта
    await export.check_access(callback.from_user.id, callback_data.account_id)
    await state.set_state(ExportStates.date)
    await state.set_data({"account_id": callback_data.account_id})
    await callback.answer()
    await edit_or_answer(callback, texts.ASK_DATE, menus.back_to_account(callback_data.account_id))


@router.message(ExportStates.date, F.text)
async def receive_date(message: Message, state: FSMContext, export: ExportDailyConversations) -> None:
    account_id: int = (await state.get_data())["account_id"]
    day = parse_day(message.text, export.today())
    if day is None:
        await message.answer(texts.INVALID_DATE, reply_markup=menus.back_to_account(account_id))
        return
    await state.clear()
    await _run_export(message, export, message.from_user.id, account_id, day, refresh=False)


async def _run_export(
    chat_message: Message,
    export: ExportDailyConversations,
    user_id: int,
    account_id: int,
    day: date,
    *,
    refresh: bool,
) -> None:
    status = await chat_message.answer(texts.export_started(day))
    try:
        summary = await export.execute(user_id, account_id, day, refresh=refresh)
    finally:
        with contextlib.suppress(TelegramBadRequest):
            await status.delete()
    await chat_message.answer(
        texts.export_summary(
            summary.account.display_name,
            day,
            summary.conversations_count,
            summary.messages_count,
            summary.exported_at,
            summary.from_cache,
            summary.day.timezone,
        ),
        reply_markup=menus.export_done(account_id, day, can_refresh=day == export.today()),
    )
