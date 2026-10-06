"""Шаги диалога с пользователем: ожидание ввода времени автовыгрузки или часового пояса."""
from aiogram.fsm.state import State, StatesGroup


class SettingsStates(StatesGroup):
    timezone = State()


class AutoExportStates(StatesGroup):
    time = State()
