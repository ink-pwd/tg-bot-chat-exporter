from datetime import date
from typing import Protocol

from domain.entities.export_schedule import ExportSchedule


class ExportScheduleRepository(Protocol):
    """Одна автовыгрузка на пользователя: все его беседы одним файлом."""

    async def get(self, owner_id: int) -> ExportSchedule | None: ...

    async def list_enabled(self) -> list[ExportSchedule]:
        """Для планировщика: все включённые расписания всех пользователей."""
        ...

    async def save(self, schedule: ExportSchedule) -> None: ...

    async def mark_done(self, owner_id: int, day: date) -> None: ...

    async def disable(self, owner_id: int) -> None: ...
