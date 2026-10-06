"""Беседа, в которую добавлен бот: владелец, статус и кто в ней отвечает от поддержки."""
from dataclasses import dataclass

from domain.enums.chat_type import ChatType


@dataclass(frozen=True)
class SupportChat:
    """Беседа, в которую добавлен бот. Владелец — тот, кто добавил бота."""

    id: int  # внутренний id; не меняется, даже когда группа становится супергруппой
    telegram_chat_id: int
    owner_id: int
    title: str
    chat_type: ChatType
    active: bool  # False — бота удалили из беседы, сохранённая история остаётся
    admin_ids: frozenset[int]  # последний известный список админов (поддержка)

    def support_ids(self) -> frozenset[int]:
        """Кто в беседе отвечает от поддержки: админы, владелец и анонимные админы.

        Сообщение анонимного админа приходит от имени самой беседы.
        """
        return self.admin_ids | {self.owner_id, self.telegram_chat_id}
