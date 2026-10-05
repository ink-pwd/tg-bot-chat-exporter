from typing import Protocol

from domain.entities.telegram_account import TelegramAccount
from domain.value_objects.telegram_profile import TelegramProfile


class TelegramAccountRepository(Protocol):
    """Доступ к аккаунтам только в рамках владельца.

    Метода «получить аккаунт по id» без владельца нет намеренно.
    """

    async def list_owned(self, owner_id: int) -> list[TelegramAccount]: ...

    async def get_owned(self, account_id: int, owner_id: int) -> TelegramAccount | None: ...

    async def save_authorized(self, owner_id: int, profile: TelegramProfile) -> TelegramAccount:
        """Создаёт аккаунт или обновляет профиль и делает его активным.

        Raises:
            AccountOwnedByAnotherUser: этот Telegram-аккаунт подключён другим пользователем.
        """
        ...

    async def delete_owned(self, account_id: int, owner_id: int) -> None: ...
