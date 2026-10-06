from datetime import timedelta
from typing import Protocol

from application.dto.export import CachedExport
from domain.value_objects.day_range import DayRange


class ExportCache(Protocol):
    """Кеш по (пользователь, день, часовой пояс): файлы, уже отправленные этому пользователю."""

    async def get(self, owner_id: int, day: DayRange) -> CachedExport | None: ...

    async def put(self, owner_id: int, day: DayRange, export: CachedExport, ttl: timedelta) -> None: ...

    async def delete(self, owner_id: int, day: DayRange) -> None: ...
