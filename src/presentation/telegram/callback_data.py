"""Данные inline-кнопок (что нажато и с какими параметрами)."""
from aiogram.filters.callback_data import CallbackData


class MenuCallback(CallbackData, prefix="menu"):
    action: str  # main | chats | settings


class ChatCallback(CallbackData, prefix="chat"):
    """chat_id приходит от клиента и может быть подделан — владелец проверяется в use case."""

    action: str  # open | disconnect | disconnect_confirm
    chat_id: int


class ExportCallback(CallbackData, prefix="exp"):
    """day приходит от клиента: окно в 7 дней проверяется в use case."""

    action: str  # days | day | refresh
    day: str = ""  # YYYY-MM-DD для day и refresh


class SettingsCallback(CallbackData, prefix="set"):
    action: str  # tz_menu | tz | tz_manual | tz_keep
    value: str = ""  # IANA-имя пояса для action=tz


class AutoExportCallback(CallbackData, prefix="auto"):
    action: str  # open | set | ask | off
    value: str = ""  # HHMM для action=set
