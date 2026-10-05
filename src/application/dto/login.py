from dataclasses import dataclass
from enum import StrEnum

from domain.entities.telegram_account import TelegramAccount
from domain.value_objects.telegram_profile import TelegramProfile
from domain.value_objects.telegram_session import TelegramSession


class CodeDelivery(StrEnum):
    APP = "app"
    SMS = "sms"
    CALL = "call"
    FLASH_CALL = "flash_call"
    MISSED_CALL = "missed_call"
    EMAIL = "email"
    FRAGMENT = "fragment"
    OTHER = "other"


@dataclass(frozen=True)
class CodeSent:
    delivery: CodeDelivery
    length: int | None


@dataclass(frozen=True)
class QrChallenge:
    url: str


@dataclass(frozen=True)
class AuthorizedSession:
    """Результат успешной авторизации в шлюзе."""

    profile: TelegramProfile
    session: TelegramSession


# --- исходы шагов входа -------------------------------------------------


@dataclass(frozen=True)
class LoginCompleted:
    account: TelegramAccount


@dataclass(frozen=True)
class PasswordRequired:
    pass


@dataclass(frozen=True)
class QrRefreshed:
    """Старый QR-код истёк, показать новый."""

    url: str


@dataclass(frozen=True)
class LoginTimedOut:
    pass


@dataclass(frozen=True)
class LoginCancelled:
    pass


SignInOutcome = AuthorizedSession | PasswordRequired
QrWaitOutcome = AuthorizedSession | PasswordRequired | QrRefreshed | LoginTimedOut | LoginCancelled

LoginStepResult = LoginCompleted | PasswordRequired
QrStepResult = LoginCompleted | PasswordRequired | QrRefreshed | LoginTimedOut | LoginCancelled
