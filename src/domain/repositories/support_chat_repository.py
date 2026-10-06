from typing import Protocol

from domain.entities.support_chat import SupportChat
from domain.enums.chat_type import ChatType


class SupportChatRepository(Protocol):
    """Беседы с ботом.

    Всё, что видит пользователь, читается только с проверкой владельца (*_owned).
    Поиск по Telegram id без владельца нужен только для приёма сообщений из беседы.
    """

    async def list_owned(self, owner_id: int) -> list[SupportChat]: ...

    async def get_owned(self, chat_id: int, owner_id: int) -> SupportChat | None: ...

    async def find_active(self, telegram_chat_id: int) -> SupportChat | None: ...

    async def connect(
        self, telegram_chat_id: int, owner_id: int, title: str, chat_type: ChatType
    ) -> SupportChat:
        """Бота добавили в беседу: создаёт её или снова делает активной.

        Если раньше беседа принадлежала другому пользователю, её история удаляется:
        новый владелец не должен получить сообщения, собранные до него.
        """
        ...

    async def deactivate(self, telegram_chat_id: int) -> None:
        """Бота удалили из беседы: новые сообщения больше не приходят, история остаётся."""
        ...

    async def migrate(self, old_telegram_chat_id: int, new_telegram_chat_id: int) -> None:
        """Группа стала супергруппой и получила новый Telegram id."""
        ...

    async def rename(self, telegram_chat_id: int, title: str) -> None: ...

    async def save_admin_ids(self, chat_id: int, admin_ids: frozenset[int]) -> None: ...

    async def delete_owned(self, chat_id: int, owner_id: int) -> None:
        """Удаляет беседу вместе со всей её историей."""
        ...
