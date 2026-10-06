from datetime import datetime
from typing import Protocol

from domain.entities.support_message import SupportMessage
from domain.value_objects.day_range import DayRange


class ChatMessageRepository(Protocol):
    """Сообщения бесед. chat_id сюда попадает только после проверки владельца."""

    async def add(self, chat_id: int, message: SupportMessage) -> None:
        """Сохраняет новое сообщение; повторная доставка того же сообщения не дублирует его."""
        ...

    async def update_edited(self, message: SupportMessage) -> None:
        """Обновляет текст отредактированного сообщения, если оно сохранено."""
        ...

    async def list_for_day(self, chat_ids: list[int], day: DayRange) -> dict[int, list[SupportMessage]]:
        """Сообщения бесед за день по chat_id, от старых к новым."""
        ...

    async def delete_sent_before(self, moment: datetime) -> int:
        """Удаляет сообщения старше срока хранения; возвращает, сколько удалено."""
        ...
