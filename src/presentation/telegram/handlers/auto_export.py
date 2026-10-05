from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from application.services.user_timezones import UserTimezones
from application.use_cases.configure_auto_export import ConfigureAutoExport
from application.use_cases.manage_telegram_accounts import ManageTelegramAccounts
from presentation.telegram import texts
from presentation.telegram.callbacks import AutoExportCallback
from presentation.telegram.date_input import parse_time
from presentation.telegram.handlers.common import edit_or_answer
from presentation.telegram.keyboards import menus
from presentation.telegram.states import AutoExportStates

router = Router(name="auto_export")


@router.callback_query(AutoExportCallback.filter(F.action == "open"))
async def open_auto_export(
    callback: CallbackQuery,
    callback_data: AutoExportCallback,
    state: FSMContext,
    accounts: ManageTelegramAccounts,
    auto_export: ConfigureAutoExport,
    timezones: UserTimezones,
) -> None:
    await state.clear()
    await callback.answer()
    await _show(callback, callback_data.account_id, accounts, auto_export, timezones)


@router.callback_query(AutoExportCallback.filter(F.action == "set"))
async def set_preset_time(
    callback: CallbackQuery,
    callback_data: AutoExportCallback,
    accounts: ManageTelegramAccounts,
    auto_export: ConfigureAutoExport,
    timezones: UserTimezones,
) -> None:
    local_time = parse_time(f"{callback_data.value[:2]}:{callback_data.value[2:]}")
    if local_time is None:  # callback_data можно подделать
        await callback.answer(texts.INVALID_TIME, show_alert=True)
        return
    await auto_export.set_time(callback.from_user.id, callback_data.account_id, local_time)
    await callback.answer(f"Автовыгрузка в {local_time:%H:%M}")
    await _show(callback, callback_data.account_id, accounts, auto_export, timezones)


@router.callback_query(AutoExportCallback.filter(F.action == "ask"))
async def ask_time(
    callback: CallbackQuery,
    callback_data: AutoExportCallback,
    state: FSMContext,
    auto_export: ConfigureAutoExport,
) -> None:
    # владелец проверяется до того, как спрашивать время
    await auto_export.get(callback.from_user.id, callback_data.account_id)
    await state.set_state(AutoExportStates.time)
    await state.set_data({"account_id": callback_data.account_id})
    await callback.answer()
    await edit_or_answer(
        callback, texts.ASK_SCHEDULE_TIME, menus.auto_export_cancel(callback_data.account_id)
    )


@router.message(AutoExportStates.time, F.text)
async def receive_time(
    message: Message,
    state: FSMContext,
    accounts: ManageTelegramAccounts,
    auto_export: ConfigureAutoExport,
    timezones: UserTimezones,
) -> None:
    account_id: int = (await state.get_data())["account_id"]
    local_time = parse_time(message.text)
    if local_time is None:
        await message.answer(texts.INVALID_TIME, reply_markup=menus.auto_export_cancel(account_id))
        return
    user_id = message.from_user.id
    schedule = await auto_export.set_time(user_id, account_id, local_time)
    await state.clear()
    account = await accounts.get(user_id, account_id)
    await message.answer(
        texts.auto_export(account, schedule, await timezones.get(user_id)),
        reply_markup=menus.auto_export(account_id, schedule),
    )


@router.callback_query(AutoExportCallback.filter(F.action == "off"))
async def disable(
    callback: CallbackQuery,
    callback_data: AutoExportCallback,
    accounts: ManageTelegramAccounts,
    auto_export: ConfigureAutoExport,
    timezones: UserTimezones,
) -> None:
    await auto_export.disable(callback.from_user.id, callback_data.account_id)
    await callback.answer("Автовыгрузка выключена")
    await _show(callback, callback_data.account_id, accounts, auto_export, timezones)


async def _show(
    callback: CallbackQuery,
    account_id: int,
    accounts: ManageTelegramAccounts,
    auto_export: ConfigureAutoExport,
    timezones: UserTimezones,
) -> None:
    user_id = callback.from_user.id
    account = await accounts.get(user_id, account_id)
    schedule = await auto_export.get(user_id, account_id)
    await edit_or_answer(
        callback,
        texts.auto_export(account, schedule, await timezones.get(user_id)),
        menus.auto_export(account_id, schedule),
    )
