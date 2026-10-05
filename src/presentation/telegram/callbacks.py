from aiogram.filters.callback_data import CallbackData


class MenuCallback(CallbackData, prefix="menu"):
    action: str  # main | accounts | add


class AccountCallback(CallbackData, prefix="acc"):
    """account_id приходит от клиента и может быть подделан — владелец проверяется в use case."""

    action: str  # open | logout | logout_confirm
    account_id: int


class LoginCallback(CallbackData, prefix="login"):
    action: str  # qr | phone | resend | cancel


class KeypadCallback(CallbackData, prefix="kp"):
    key: str  # 0-9 | del | ok


class ExportCallback(CallbackData, prefix="exp"):
    """День считается в момент нажатия: «today»/«yesterday» не устаревают после полуночи."""

    action: str  # today | yesterday | ask_date | refresh
    account_id: int
    day: str = ""  # YYYY-MM-DD, только для refresh
