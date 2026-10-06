from datetime import date, time

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from domain.entities.export_schedule import ExportSchedule
from domain.entities.support_chat import SupportChat
from presentation.telegram.callbacks import (
    AutoExportCallback,
    ChatCallback,
    ExportCallback,
    MenuCallback,
    SettingsCallback,
)

TIMEZONE_PRESETS = [
    ("Киев", "Europe/Kyiv"),
    ("Варшава", "Europe/Warsaw"),
    ("Берлин", "Europe/Berlin"),
    ("Лондон", "Europe/London"),
    ("Лиссабон", "Europe/Lisbon"),
    ("Стамбул", "Europe/Istanbul"),
    ("Тбилиси", "Asia/Tbilisi"),
    ("Дубай", "Asia/Dubai"),
    ("Алматы", "Asia/Almaty"),
    ("Нью-Йорк", "America/New_York"),
    ("UTC", "UTC"),
]

TIME_PRESETS = [time(0, 30), time(6, 0), time(7, 0), time(8, 0), time(9, 0), time(10, 0)]


def add_to_group_url(bot_username: str) -> str:
    return f"https://t.me/{bot_username}?startgroup=connect"


def main_menu(
    chats: list[SupportChat], schedule: ExportSchedule, bot_username: str
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    sizes = []
    if chats:
        kb.button(text="📥 Выгрузить", callback_data=ExportCallback(action="days"))
        kb.button(text=f"💬 Мои беседы ({len(chats)})", callback_data=MenuCallback(action="chats"))
        sizes += [1, 1]
    kb.button(text="➕ Добавить в беседу", url=add_to_group_url(bot_username))
    auto = schedule.local_time.strftime("%H:%M") if schedule.enabled else "выкл"
    kb.button(text=f"⏰ Автовыгрузка: {auto}", callback_data=AutoExportCallback(action="open"))
    kb.button(text="⚙️ Настройки", callback_data=MenuCallback(action="settings"))
    kb.adjust(*sizes, 1, 1, 1)
    return kb.as_markup()


def back_to_main() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="« В меню", callback_data=MenuCallback(action="main"))
    return kb.as_markup()


def chats_list(chats: list[SupportChat], bot_username: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for chat in chats:
        mark = "" if chat.active else "⚠️ "
        kb.button(text=f"{mark}{chat.title}", callback_data=ChatCallback(action="open", chat_id=chat.id))
    kb.button(text="➕ Добавить в беседу", url=add_to_group_url(bot_username))
    kb.button(text="« В меню", callback_data=MenuCallback(action="main"))
    kb.adjust(1)
    return kb.as_markup()


def chat_card(chat: SupportChat) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="🗑 Отключить и удалить сообщения",
        callback_data=ChatCallback(action="disconnect", chat_id=chat.id),
    )
    kb.button(text="« К беседам", callback_data=MenuCallback(action="chats"))
    kb.adjust(1)
    return kb.as_markup()


def disconnect_confirm(chat: SupportChat) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="Да, отключить",
        callback_data=ChatCallback(action="disconnect_confirm", chat_id=chat.id),
    )
    kb.button(text="Отмена", callback_data=ChatCallback(action="open", chat_id=chat.id))
    kb.adjust(2)
    return kb.as_markup()


def auto_export(schedule: ExportSchedule) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for preset in TIME_PRESETS:
        selected = schedule.enabled and schedule.local_time == preset
        kb.button(
            text=("✅ " if selected else "") + preset.strftime("%H:%M"),
            callback_data=AutoExportCallback(action="set", value=preset.strftime("%H%M")),
        )
    kb.button(text="✏️ Другое время", callback_data=AutoExportCallback(action="ask"))
    if schedule.enabled:
        kb.button(text="⏹ Выключить", callback_data=AutoExportCallback(action="off"))
    kb.button(text="« В меню", callback_data=MenuCallback(action="main"))
    kb.adjust(3, 3, 1, 1, 1)
    return kb.as_markup()


def auto_export_cancel() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Отмена", callback_data=AutoExportCallback(action="open"))
    return kb.as_markup()


def settings_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🌍 Часовой пояс", callback_data=SettingsCallback(action="tz_menu"))
    kb.button(text="« Назад", callback_data=MenuCallback(action="main"))
    kb.adjust(1)
    return kb.as_markup()


def timezone_choices(current: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for label, name in TIMEZONE_PRESETS:
        kb.button(
            text=("✅ " if name == current else "") + label,
            callback_data=SettingsCallback(action="tz", value=name),
        )
    kb.button(text="✏️ Ввести вручную", callback_data=SettingsCallback(action="tz_manual"))
    kb.button(text="« Назад", callback_data=MenuCallback(action="settings"))
    kb.adjust(*[3] * (len(TIMEZONE_PRESETS) // 3), len(TIMEZONE_PRESETS) % 3 or 3, 1, 1)
    return kb.as_markup()


def timezone_input_cancel() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Отмена", callback_data=SettingsCallback(action="tz_menu"))
    return kb.as_markup()


def schedule_time_after_timezone_change() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⏰ Изменить время", callback_data=AutoExportCallback(action="open"))
    kb.button(text="Оставить как есть", callback_data=SettingsCallback(action="tz_keep"))
    kb.adjust(1)
    return kb.as_markup()


def export_days(days: list[date], labels: list[str]) -> InlineKeyboardMarkup:
    """days — от сегодня назад; сегодня и вчера на всю ширину, остальные по два."""
    kb = InlineKeyboardBuilder()
    for day, label in zip(days, labels):
        kb.button(text=label, callback_data=ExportCallback(action="day", day=day.isoformat()))
    kb.button(text="« В меню", callback_data=MenuCallback(action="main"))
    kb.adjust(1, 1, 2, 2, 1, 1)
    return kb.as_markup()


def export_done(day: date, can_refresh: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if can_refresh:
        kb.button(
            text="🔄 Обновить",
            callback_data=ExportCallback(action="refresh", day=day.isoformat()),
        )
    kb.button(text="📥 Другой день", callback_data=ExportCallback(action="days"))
    kb.button(text="« В меню", callback_data=MenuCallback(action="main"))
    kb.adjust(1)
    return kb.as_markup()
