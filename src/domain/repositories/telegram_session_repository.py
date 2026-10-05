from typing import Protocol

from domain.value_objects.telegram_session import TelegramSession


class TelegramSessionRepository(Protocol):
    """Хранилище сессий. account_id сюда попадает только после проверки владельца."""

    async def save(self, account_id: int, session: TelegramSession) -> None: ...

    async def get(self, account_id: int) -> TelegramSession | None: ...

    async def delete(self, account_id: int) -> None: ...
