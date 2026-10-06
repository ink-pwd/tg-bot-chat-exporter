from aiogram.fsm.state import State, StatesGroup


class SettingsStates(StatesGroup):
    timezone = State()


class AutoExportStates(StatesGroup):
    time = State()
