"""Меню настроек: выбор часового пояса и вопрос о времени автовыгрузки после его смены."""
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from application.services.user_timezones import UserTimezones
from application.use_cases.configure_auto_export import ConfigureAutoExport
from domain.business_rule_errors import InvalidTimezone
from presentation.telegram import bot_texts
from presentation.telegram.callback_data import MenuCallback, SettingsCallback
from presentation.telegram.dialog_states import SettingsStates
from presentation.telegram.handlers.main_menu_and_errors import edit_or_answer
from presentation.telegram.keyboards import menu_keyboards

router = Router(name="preferences_menu")


@router.callback_query(MenuCallback.filter(F.action == "settings"))
async def open_settings(callback: CallbackQuery, state: FSMContext, timezones: UserTimezones) -> None:
    await state.clear()
    await callback.answer()
    timezone = await timezones.get(callback.from_user.id)
    await edit_or_answer(callback, bot_texts.settings(timezone), menu_keyboards.settings_menu())


@router.callback_query(SettingsCallback.filter(F.action == "tz_menu"))
async def timezone_menu(callback: CallbackQuery, state: FSMContext, timezones: UserTimezones) -> None:
    await state.clear()
    await callback.answer()
    timezone = await timezones.get(callback.from_user.id)
    await edit_or_answer(callback, bot_texts.timezone_menu(timezone), menu_keyboards.timezone_choices(timezone.key))


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
    await edit_or_answer(callback, bot_texts.ASK_TIMEZONE, menu_keyboards.timezone_input_cancel())


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
        await message.answer(bot_texts.error_text(exc), reply_markup=menu_keyboards.timezone_input_cancel())
        return
    await state.clear()
    text, markup = await _after_change(message.from_user.id, timezone, auto_export)
    await message.answer(text, reply_markup=markup)


@router.callback_query(SettingsCallback.filter(F.action == "tz_keep"))
async def keep_time(callback: CallbackQuery) -> None:
    await callback.answer()
    await edit_or_answer(callback, bot_texts.TIMEZONE_KEPT, menu_keyboards.settings_menu())


async def _after_change(
    user_id: int, timezone: ZoneInfo, auto_export: ConfigureAutoExport
) -> tuple[str, InlineKeyboardMarkup]:
    """Если автовыгрузка включена — спрашиваем, менять ли её время под новый пояс."""
    schedule = await auto_export.get(user_id)
    if not schedule.enabled:
        return bot_texts.timezone_changed(timezone), menu_keyboards.settings_menu()
    return (
        bot_texts.ask_change_schedule_time(timezone, schedule),
        menu_keyboards.schedule_time_after_timezone_change(),
    )
