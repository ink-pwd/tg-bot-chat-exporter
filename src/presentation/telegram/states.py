from aiogram.fsm.state import State, StatesGroup


class LoginStates(StatesGroup):
    phone = State()
    code = State()
    password = State()


class ExportStates(StatesGroup):
    date = State()
