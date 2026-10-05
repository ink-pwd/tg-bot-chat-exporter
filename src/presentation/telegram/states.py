from aiogram.fsm.state import State, StatesGroup


class LoginStates(StatesGroup):
    phone = State()
    code = State()
    password = State()


class ExportStates(StatesGroup):
    date = State()


class SettingsStates(StatesGroup):
    timezone = State()


class AutoExportStates(StatesGroup):
    time = State()
