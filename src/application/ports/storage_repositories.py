"""Хранилища. Реализации — в infrastructure/persistence (MySQL)."""
from datetime import date, datetime
from typing import Protocol

from domain.entities.export_schedule import ExportSchedule
from domain.entities.support_chat import SupportChat
from domain.entities.support_message import SupportMessage
from domain.enums.chat_type import ChatType
from domain.value_objects.day_range import DayRange


class BotUserRepository(Protocol):
    async def ensure_exists(self, user_id: int) -> None: ...

    async def get_timezone(self, user_id: int) -> str | None:
        """IANA-имя пояса (Europe/Kyiv) или None, если пользователь его не выбирал."""
        ...

    async def set_timezone(self, user_id: int, timezone: str) -> None: ...


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


class ExportScheduleRepository(Protocol):
    """Одна автовыгрузка на пользователя: все его беседы одним файлом."""

    async def get(self, owner_id: int) -> ExportSchedule | None: ...

    async def list_enabled(self) -> list[ExportSchedule]:
        """Для планировщика: все включённые расписания всех пользователей."""
        ...

    async def save(self, schedule: ExportSchedule) -> None: ...

    async def mark_done(self, owner_id: int, day: date) -> None: ...

    async def disable(self, owner_id: int) -> None: ...
