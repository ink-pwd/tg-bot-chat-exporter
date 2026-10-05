from datetime import timedelta
from typing import Protocol

from application.dto.export import CachedExport
from domain.value_objects.day_range import DayRange


class ExportCache(Protocol):
    """Кеш по (account_id, день, часовой пояс). Читается только после проверки владельца."""

    async def get(self, account_id: int, day: DayRange) -> CachedExport | None: ...

    async def put(self, account_id: int, day: DayRange, export: CachedExport, ttl: timedelta) -> None: ...

    async def delete(self, account_id: int, day: DayRange) -> None: ...
