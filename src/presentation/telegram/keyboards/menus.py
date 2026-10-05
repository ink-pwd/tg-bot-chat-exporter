from datetime import date

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from domain.entities.telegram_account import TelegramAccount
from domain.enums.account_status import AccountStatus
from presentation.telegram.callbacks import (
    AccountCallback,
    ExportCallback,
    KeypadCallback,
    LoginCallback,
    MenuCallback,
)


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📱 Мои аккаунты", callback_data=MenuCallback(action="accounts"))
    kb.button(text="➕ Подключить аккаунт", callback_data=MenuCallback(action="add"))
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


def account_card(account: TelegramAccount) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if account.status is AccountStatus.REVOKED:
        kb.button(text="🔑 Подключить заново", callback_data=MenuCallback(action="add"))
        sizes = [1]
    else:
        kb.button(text="📅 Сегодня", callback_data=ExportCallback(action="today", account_id=account.id))
        kb.button(text="📅 Вчера", callback_data=ExportCallback(action="yesterday", account_id=account.id))
        kb.button(text="🗓 Другая дата", callback_data=ExportCallback(action="ask_date", account_id=account.id))
        sizes = [2, 1]
    kb.button(
        text="🚪 Отключить аккаунт",
        callback_data=AccountCallback(action="logout", account_id=account.id),
    )
    kb.button(text="« К аккаунтам", callback_data=MenuCallback(action="accounts"))
    kb.adjust(*sizes, 1, 1)
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
