from datetime import date
from typing import Protocol

from domain.entities.export_schedule import ExportSchedule


class ExportScheduleRepository(Protocol):
    async def get_owned(self, account_id: int, owner_id: int) -> ExportSchedule | None: ...

    async def list_owned(self, owner_id: int) -> list[ExportSchedule]: ...

    async def list_enabled(self) -> list[ExportSchedule]:
        """Для планировщика: все включённые расписания всех пользователей."""
        ...

    async def save(self, schedule: ExportSchedule) -> None:
        """Сохраняет расписание, только если аккаунт принадлежит schedule.owner_id."""
        ...

    async def mark_done(self, account_id: int, day: date) -> None: ...

    async def disable(self, account_id: int) -> None: ...

    async def disable_all_owned(self, owner_id: int) -> None: ...
