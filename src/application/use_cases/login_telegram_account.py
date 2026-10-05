import logging

from application.dto.login import (
    AuthorizedSession,
    CodeSent,
    LoginCompleted,
    LoginStepResult,
    QrChallenge,
    QrStepResult,
)
from application.interfaces.telegram_auth_gateway import TelegramAuthGateway
from domain.errors import AccountOwnedByAnotherUser
from domain.repositories.bot_user_repository import BotUserRepository
from domain.repositories.telegram_account_repository import TelegramAccountRepository
from domain.repositories.telegram_session_repository import TelegramSessionRepository
from domain.value_objects.phone_number import PhoneNumber

logger = logging.getLogger(__name__)


class LoginTelegramAccount:
    """Подключение Telegram-аккаунта к пользователю бота (QR или телефон + код)."""

    def __init__(
        self,
        gateway: TelegramAuthGateway,
        users: BotUserRepository,
        accounts: TelegramAccountRepository,
        sessions: TelegramSessionRepository,
    ) -> None:
        self._gateway = gateway
        self._users = users
        self._accounts = accounts
        self._sessions = sessions

    async def start_qr(self, user_id: int) -> QrChallenge:
        logger.info("Account login started: user=%s method=qr", user_id)
        return await self._gateway.start_qr(user_id)

    async def wait_qr(self, user_id: int) -> QrStepResult:
        outcome = await self._gateway.wait_qr(user_id)
        if isinstance(outcome, AuthorizedSession):
            return await self._complete(user_id, outcome)
        return outcome

    async def start_phone(self, user_id: int, raw_phone: str) -> CodeSent:
        phone = PhoneNumber.parse(raw_phone)
        logger.info("Account login started: user=%s method=phone", user_id)
        return await self._gateway.start_phone(user_id, phone)

    async def resend_code(self, user_id: int) -> CodeSent:
        return await self._gateway.resend_code(user_id)

    async def submit_code(self, user_id: int, code: str) -> LoginStepResult:
        outcome = await self._gateway.submit_code(user_id, code)
        if isinstance(outcome, AuthorizedSession):
            return await self._complete(user_id, outcome)
        return outcome

    async def submit_password(self, user_id: int, password: str) -> LoginStepResult:
        outcome = await self._gateway.submit_password(user_id, password)
        if isinstance(outcome, AuthorizedSession):
            return await self._complete(user_id, outcome)
        return outcome

    async def cancel(self, user_id: int) -> None:
        await self._gateway.cancel(user_id)

    async def _complete(self, user_id: int, authorized: AuthorizedSession) -> LoginCompleted:
        await self._users.ensure_exists(user_id)
        try:
            account = await self._accounts.save_authorized(user_id, authorized.profile)
        except AccountOwnedByAnotherUser:
            logger.warning(
                "Account login rejected: user=%s, account already owned by another user", user_id
            )
            # новая сессия не должна остаться висеть в «Устройствах» чужого владельца
            await self._gateway.log_out(authorized.session)
            raise
        await self._sessions.save(account.id, authorized.session)
        logger.info("Account authenticated: user=%s account=%s", user_id, account.id)
        return LoginCompleted(account)
