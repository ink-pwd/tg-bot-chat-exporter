import logging

from application.errors import ApplicationError
from application.interfaces.telegram_auth_gateway import TelegramAuthGateway
from domain.entities.telegram_account import TelegramAccount
from domain.errors import AccountNotFound
from domain.repositories.telegram_account_repository import TelegramAccountRepository
from domain.repositories.telegram_session_repository import TelegramSessionRepository

logger = logging.getLogger(__name__)


class ManageTelegramAccounts:
    """Просмотр и отключение своих аккаунтов."""

    def __init__(
        self,
        gateway: TelegramAuthGateway,
        accounts: TelegramAccountRepository,
        sessions: TelegramSessionRepository,
    ) -> None:
        self._gateway = gateway
        self._accounts = accounts
        self._sessions = sessions

    async def list(self, user_id: int) -> list[TelegramAccount]:
        return await self._accounts.list_owned(user_id)

    async def get(self, user_id: int, account_id: int) -> TelegramAccount:
        account = await self._accounts.get_owned(account_id, user_id)
        if account is None:
            raise AccountNotFound()
        return account

    async def log_out(self, user_id: int, account_id: int) -> None:
        account = await self.get(user_id, account_id)
        session = await self._sessions.get(account.id)
        if session is not None:
            try:
                await self._gateway.log_out(session)
            except ApplicationError:
                # сессию всё равно удаляем у себя: доступ через бота должен пропасть
                logger.warning("Telegram log out failed: account=%s", account.id, exc_info=True)
        await self._sessions.delete(account.id)
        await self._accounts.delete_owned(account.id, user_id)
        logger.info("Account logged out: user=%s account=%s", user_id, account.id)
