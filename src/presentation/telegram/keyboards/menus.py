from datetime import date, time

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from domain.entities.export_schedule import ExportSchedule
from domain.entities.telegram_account import TelegramAccount
from domain.enums.account_status import AccountStatus
from presentation.telegram.callbacks import (
    AccountCallback,
    AutoExportCallback,
    ExportCallback,
    KeypadCallback,
    LoginCallback,
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


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📱 Мои аккаунты", callback_data=MenuCallback(action="accounts"))
    kb.button(text="➕ Подключить аккаунт", callback_data=MenuCallback(action="add"))
    kb.button(text="⚙️ Настройки", callback_data=MenuCallback(action="settings"))
    kb.adjust(1)
    return kb.as_markup()


def accounts_list(accounts: list[TelegramAccount]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for account in accounts:
        mark = "⚠️ " if account.status is AccountStatus.REVOKED else ""
        kb.button(
            text=f"{mark}{account.display_name}",
            callback_data=AccountCallback(action="open", account_id=account.id),
        )
    kb.button(text="➕ Подключить аккаунт", callback_data=MenuCallback(action="add"))
    kb.button(text="« Назад", callback_data=MenuCallback(action="main"))
    kb.adjust(1)
    return kb.as_markup()


def account_card(account: TelegramAccount, schedule: ExportSchedule) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if account.status is AccountStatus.REVOKED:
        kb.button(text="🔑 Подключить заново", callback_data=MenuCallback(action="add"))
        sizes = [1]
    else:
        kb.button(text="📅 Сегодня", callback_data=ExportCallback(action="today", account_id=account.id))
        kb.button(text="📅 Вчера", callback_data=ExportCallback(action="yesterday", account_id=account.id))
        kb.button(text="🗓 Другая дата", callback_data=ExportCallback(action="ask_date", account_id=account.id))
        auto = schedule.local_time.strftime("%H:%M") if schedule.enabled else "выкл"
        kb.button(
            text=f"⏰ Автовыгрузка: {auto}",
            callback_data=AutoExportCallback(action="open", account_id=account.id),
        )
        sizes = [2, 1, 1]
    kb.button(
        text="🚪 Отключить аккаунт",
        callback_data=AccountCallback(action="logout", account_id=account.id),
    )
    kb.button(text="« К аккаунтам", callback_data=MenuCallback(action="accounts"))
    kb.adjust(*sizes, 1, 1)
    return kb.as_markup()


def auto_export(account_id: int, schedule: ExportSchedule) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for preset in TIME_PRESETS:
        selected = schedule.enabled and schedule.local_time == preset
        kb.button(
            text=("✅ " if selected else "") + preset.strftime("%H:%M"),
            callback_data=AutoExportCallback(
                action="set", account_id=account_id, value=preset.strftime("%H%M")
            ),
        )
    kb.button(text="✏️ Другое время", callback_data=AutoExportCallback(action="ask", account_id=account_id))
    if schedule.enabled:
        kb.button(text="⏹ Выключить", callback_data=AutoExportCallback(action="off", account_id=account_id))
    kb.button(text="« К аккаунту", callback_data=AccountCallback(action="open", account_id=account_id))
    kb.adjust(3, 3, 1, 1, 1)
    return kb.as_markup()


def auto_export_cancel(account_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Отмена", callback_data=AutoExportCallback(action="open", account_id=account_id))
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


def schedule_times_after_timezone_change() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⏰ Изменить время", callback_data=SettingsCallback(action="tz_change"))
    kb.button(text="Оставить как есть", callback_data=SettingsCallback(action="tz_keep"))
    kb.adjust(1)
    return kb.as_markup()


def scheduled_accounts(items: list[tuple[TelegramAccount, ExportSchedule]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for account, schedule in items:
        kb.button(
            text=f"{account.display_name} — {schedule.local_time:%H:%M}",
            callback_data=AutoExportCallback(action="open", account_id=account.id),
        )
    kb.button(text="« В меню", callback_data=MenuCallback(action="main"))
    kb.adjust(1)
    return kb.as_markup()


def export_done(account_id: int, day: date, can_refresh: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if can_refresh:
        kb.button(
            text="🔄 Обновить",
            callback_data=ExportCallback(action="refresh", account_id=account_id, day=day.isoformat()),
        )
    kb.button(text="« К аккаунту", callback_data=AccountCallback(action="open", account_id=account_id))
    kb.adjust(1)
    return kb.as_markup()


def back_to_account(account_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Отмена", callback_data=AccountCallback(action="open", account_id=account_id))
    return kb.as_markup()


def logout_confirm(account: TelegramAccount) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="Да, отключить",
        callback_data=AccountCallback(action="logout_confirm", account_id=account.id),
    )
    kb.button(text="Отмена", callback_data=AccountCallback(action="open", account_id=account.id))
    kb.adjust(2)
    return kb.as_markup()


def login_methods() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔳 QR-код", callback_data=LoginCallback(action="qr"))
    kb.button(text="📞 По номеру телефона", callback_data=LoginCallback(action="phone"))
    kb.button(text="Отмена", callback_data=MenuCallback(action="main"))
    kb.adjust(1)
    return kb.as_markup()


def login_cancel() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Отмена", callback_data=LoginCallback(action="cancel"))
    return kb.as_markup()


def code_keypad() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for digit in "123456789":
        kb.button(text=digit, callback_data=KeypadCallback(key=digit))
    kb.button(text="⌫", callback_data=KeypadCallback(key="del"))
    kb.button(text="0", callback_data=KeypadCallback(key="0"))
    kb.button(text="✓", callback_data=KeypadCallback(key="ok"))
    kb.button(text="🔁 Отправить код повторно", callback_data=LoginCallback(action="resend"))
    kb.button(text="Отмена", callback_data=LoginCallback(action="cancel"))
    kb.adjust(3, 3, 3, 3, 1, 1)
    return kb.as_markup()
