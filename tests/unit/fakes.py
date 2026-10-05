"""Фейки инфраструктуры для unit-тестов use case'ов."""
from dataclasses import dataclass, field, replace

from application.dto.login import (
    AuthorizedSession,
    CodeDelivery,
    CodeSent,
    QrChallenge,
    QrWaitOutcome,
    SignInOutcome,
)
from application.errors import TelegramUnavailable
from domain.entities.telegram_account import TelegramAccount
from domain.enums.account_status import AccountStatus
from domain.errors import AccountOwnedByAnotherUser
from domain.value_objects.phone_number import PhoneNumber
from domain.value_objects.telegram_profile import TelegramProfile
from domain.value_objects.telegram_session import TelegramSession


class InMemoryBotUsers:
    def __init__(self) -> None:
        self.ids: set[int] = set()

    async def ensure_exists(self, user_id: int) -> None:
        self.ids.add(user_id)


class InMemoryAccounts:
    def __init__(self) -> None:
        self.rows: dict[int, TelegramAccount] = {}
        self._next_id = 1

    async def list_owned(self, owner_id: int) -> list[TelegramAccount]:
        return [a for a in self.rows.values() if a.owner_id == owner_id]

    async def get_owned(self, account_id: int, owner_id: int) -> TelegramAccount | None:
        account = self.rows.get(account_id)
        return account if account and account.owner_id == owner_id else None

    async def save_authorized(self, owner_id: int, profile: TelegramProfile) -> TelegramAccount:
        for account in self.rows.values():
            if account.telegram_user_id == profile.telegram_user_id:
                if account.owner_id != owner_id:
                    raise AccountOwnedByAnotherUser()
                updated = replace(
                    account,
                    display_name=profile.display_name,
                    username=profile.username,
                    status=AccountStatus.ACTIVE,
                )
                self.rows[account.id] = updated
                return updated
        account = TelegramAccount(
            id=self._next_id,
            owner_id=owner_id,
            telegram_user_id=profile.telegram_user_id,
            display_name=profile.display_name,
            username=profile.username,
            status=AccountStatus.ACTIVE,
        )
        self.rows[account.id] = account
        self._next_id += 1
        return account

    async def mark_revoked(self, account_id: int, owner_id: int) -> None:
        if (account := self.rows.get(account_id)) and account.owner_id == owner_id:
            self.rows[account_id] = replace(account, status=AccountStatus.REVOKED)

    async def delete_owned(self, account_id: int, owner_id: int) -> None:
        if (account := self.rows.get(account_id)) and account.owner_id == owner_id:
            del self.rows[account_id]

    def add(self, owner_id: int, telegram_user_id: int, name: str = "Acc") -> TelegramAccount:
        account = TelegramAccount(
            id=self._next_id,
            owner_id=owner_id,
            telegram_user_id=telegram_user_id,
            display_name=name,
            username=None,
            status=AccountStatus.ACTIVE,
        )
        self.rows[account.id] = account
        self._next_id += 1
        return account


class InMemorySessions:
    def __init__(self) -> None:
        self.rows: dict[int, TelegramSession] = {}

    async def save(self, account_id: int, session: TelegramSession) -> None:
        self.rows[account_id] = session

    async def get(self, account_id: int) -> TelegramSession | None:
        return self.rows.get(account_id)

    async def delete(self, account_id: int) -> None:
        self.rows.pop(account_id, None)


@dataclass
class FakeAuthGateway:
    """Возвращает заранее заданные исходы шагов и запоминает вызовы."""

    sign_in_outcome: SignInOutcome | None = None
    qr_outcome: QrWaitOutcome | None = None
    fail_log_out: bool = False
    logged_out: list[TelegramSession] = field(default_factory=list)
    started_phones: list[PhoneNumber] = field(default_factory=list)
    cancelled: list[int] = field(default_factory=list)

    async def start_qr(self, login_id: int) -> QrChallenge:
        return QrChallenge("tg://login?token=abc")

    async def wait_qr(self, login_id: int) -> QrWaitOutcome:
        return self.qr_outcome

    async def start_phone(self, login_id: int, phone: PhoneNumber) -> CodeSent:
        self.started_phones.append(phone)
        return CodeSent(CodeDelivery.APP, 5)

    async def resend_code(self, login_id: int) -> CodeSent:
        return CodeSent(CodeDelivery.SMS, 5)

    async def submit_code(self, login_id: int, code: str) -> SignInOutcome:
        return self.sign_in_outcome

    async def submit_password(self, login_id: int, password: str) -> SignInOutcome:
        return self.sign_in_outcome

    async def cancel(self, login_id: int) -> None:
        self.cancelled.append(login_id)

    async def log_out(self, session: TelegramSession) -> None:
        self.logged_out.append(session)
        if self.fail_log_out:
            raise TelegramUnavailable()


def authorized(telegram_user_id: int, session: str = "session", name: str = "Support") -> AuthorizedSession:
    return AuthorizedSession(
        TelegramProfile(telegram_user_id, name, None), TelegramSession(session)
    )
