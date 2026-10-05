from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from application.services.user_timezones import UserTimezones
from application.use_cases.configure_auto_export import ConfigureAutoExport
from domain.errors import InvalidTimezone
from presentation.telegram import texts
from presentation.telegram.callbacks import MenuCallback, SettingsCallback
from presentation.telegram.handlers.common import edit_or_answer
from presentation.telegram.keyboards import menus
from presentation.telegram.states import SettingsStates

router = Router(name="settings")


@router.callback_query(MenuCallback.filter(F.action == "settings"))
async def open_settings(callback: CallbackQuery, state: FSMContext, timezones: UserTimezones) -> None:
    await state.clear()
    await callback.answer()
    timezone = await timezones.get(callback.from_user.id)
    await edit_or_answer(callback, texts.settings(timezone), menus.settings_menu())


@router.callback_query(SettingsCallback.filter(F.action == "tz_menu"))
async def timezone_menu(callback: CallbackQuery, state: FSMContext, timezones: UserTimezones) -> None:
    await state.clear()
    await callback.answer()
    timezone = await timezones.get(callback.from_user.id)
    await edit_or_answer(callback, texts.timezone_menu(timezone), menus.timezone_choices(timezone.key))


@router.callback_query(SettingsCallback.filter(F.action == "tz"))
async def choose_preset(
    callback: CallbackQuery,
    callback_data: SettingsCallback,
    timezones: UserTimezones,
    auto_export: ConfigureAutoExport,
) -> None:
    timezone = await timezones.set(callback.from_user.id, callback_data.value)
    await callback.answer()
    text, markup = await _after_change(callback.from_user.id, timezone, auto_export)
    await edit_or_answer(callback, text, markup)


@router.callback_query(SettingsCallback.filter(F.action == "tz_manual"))
async def ask_timezone(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.timezone)
    await callback.answer()
    await edit_or_answer(callback, texts.ASK_TIMEZONE, menus.timezone_input_cancel())


@router.message(SettingsStates.timezone, F.text)
async def receive_timezone(
    message: Message,
    state: FSMContext,
    timezones: UserTimezones,
    auto_export: ConfigureAutoExport,
) -> None:
    try:
        timezone = await timezones.set(message.from_user.id, message.text)
    except InvalidTimezone as exc:
        await message.answer(texts.error_text(exc), reply_markup=menus.timezone_input_cancel())
        return
    await state.clear()
    text, markup = await _after_change(message.from_user.id, timezone, auto_export)
    await message.answer(text, reply_markup=markup)


@router.callback_query(SettingsCallback.filter(F.action == "tz_keep"))
async def keep_times(callback: CallbackQuery) -> None:
    await callback.answer()
    await edit_or_answer(callback, texts.TIMEZONE_KEPT, menus.main_menu())


@router.callback_query(SettingsCallback.filter(F.action == "tz_change"))
async def change_times(callback: CallbackQuery, auto_export: ConfigureAutoExport) -> None:
    await callback.answer()
    items = await auto_export.list_enabled(callback.from_user.id)
    await edit_or_answer(callback, texts.CHOOSE_SCHEDULE, menus.scheduled_accounts(items))


async def _after_change(
    user_id: int, timezone: ZoneInfo, auto_export: ConfigureAutoExport
) -> tuple[str, InlineKeyboardMarkup]:
    """Если есть автовыгрузки — спрашиваем, менять ли их время под новый пояс."""
    items = await auto_export.list_enabled(user_id)
    if not items:
        return texts.timezone_changed(timezone), menus.settings_menu()
    return texts.ask_change_schedule_times(timezone, items), menus.schedule_times_after_timezone_change()
