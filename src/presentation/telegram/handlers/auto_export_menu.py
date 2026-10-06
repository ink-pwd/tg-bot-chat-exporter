"""Меню автовыгрузки: выбор времени, ввод своего времени, выключение."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from application.services.user_timezones import UserTimezones
from application.use_cases.configure_auto_export import ConfigureAutoExport
from presentation.telegram import bot_texts
from presentation.telegram.callback_data import AutoExportCallback
from presentation.telegram.dialog_states import AutoExportStates
from presentation.telegram.handlers.main_menu_and_errors import edit_or_answer
from presentation.telegram.input.time_input_parsing import parse_time
from presentation.telegram.keyboards import menu_keyboards

router = Router(name="auto_export_menu")


@router.callback_query(AutoExportCallback.filter(F.action == "open"))
async def open_auto_export(
    callback: CallbackQuery,
    state: FSMContext,
    auto_export: ConfigureAutoExport,
    timezones: UserTimezones,
) -> None:
    await state.clear()
    await callback.answer()
    await _show(callback, auto_export, timezones)


@router.callback_query(AutoExportCallback.filter(F.action == "set"))
async def set_preset_time(
    callback: CallbackQuery,
    callback_data: AutoExportCallback,
    auto_export: ConfigureAutoExport,
    timezones: UserTimezones,
) -> None:
    local_time = parse_time(f"{callback_data.value[:2]}:{callback_data.value[2:]}")
    if local_time is None:  # callback_data можно подделать
        await callback.answer(bot_texts.INVALID_TIME, show_alert=True)
        return
    await auto_export.set_time(callback.from_user.id, local_time)
    await callback.answer(f"Автовыгрузка в {local_time:%H:%M}")
    await _show(callback, auto_export, timezones)


@router.callback_query(AutoExportCallback.filter(F.action == "ask"))
async def ask_time(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AutoExportStates.time)
    await callback.answer()
    await edit_or_answer(callback, bot_texts.ASK_SCHEDULE_TIME, menu_keyboards.auto_export_cancel())


@router.message(AutoExportStates.time, F.text)
async def receive_time(
    message: Message,
    state: FSMContext,
    auto_export: ConfigureAutoExport,
    timezones: UserTimezones,
) -> None:
    local_time = parse_time(message.text)
    if local_time is None:
        await message.answer(bot_texts.INVALID_TIME, reply_markup=menu_keyboards.auto_export_cancel())
        return
    user_id = message.from_user.id
    schedule = await auto_export.set_time(user_id, local_time)
    await state.clear()
    await message.answer(
        bot_texts.auto_export(schedule, await timezones.get(user_id)),
        reply_markup=menu_keyboards.auto_export(schedule),
    )


@router.callback_query(AutoExportCallback.filter(F.action == "off"))
async def disable(
    callback: CallbackQuery, auto_export: ConfigureAutoExport, timezones: UserTimezones
) -> None:
    await auto_export.disable(callback.from_user.id)
    await callback.answer("Автовыгрузка выключена")
    await _show(callback, auto_export, timezones)


async def _show(
    callback: CallbackQuery, auto_export: ConfigureAutoExport, timezones: UserTimezones
) -> None:
    user_id = callback.from_user.id
    schedule = await auto_export.get(user_id)
    await edit_or_answer(
        callback,
        bot_texts.auto_export(schedule, await timezones.get(user_id)),
        menu_keyboards.auto_export(schedule),
    )
