import json
from datetime import datetime, timedelta

from redis.asyncio import Redis

from application.dto.export import CachedExport
from domain.value_objects.day_range import DayRange


class RedisExportCache:
    """Хранит только file_id и счётчики — текстов переписок в Redis нет."""

    def __init__(self, redis: Redis, prefix: str = "export") -> None:
        self._redis = redis
        self._prefix = prefix

    async def get(self, account_id: int, day: DayRange) -> CachedExport | None:
        raw = await self._redis.get(self._key(account_id, day))
        if raw is None:
            return None
        data = json.loads(raw)
        if "file_ids" in data:
            file_ids = tuple(data["file_ids"])
        else:  # запись до появления отчётов: один JSON-файл
            file_ids = (data["file_id"],) if data.get("file_id") else ()
        return CachedExport(
            file_ids=file_ids,
            conversations_count=data["conversations_count"],
            messages_count=data["messages_count"],
            exported_at=datetime.fromisoformat(data["exported_at"]),
        )

    async def put(self, account_id: int, day: DayRange, export: CachedExport, ttl: timedelta) -> None:
        payload = json.dumps(
            {
                "file_ids": list(export.file_ids),
                "conversations_count": export.conversations_count,
                "messages_count": export.messages_count,
                "exported_at": export.exported_at.isoformat(),
            }
        )
        await self._redis.set(self._key(account_id, day), payload, ex=int(ttl.total_seconds()))

    async def delete(self, account_id: int, day: DayRange) -> None:
        await self._redis.delete(self._key(account_id, day))

    def _key(self, account_id: int, day: DayRange) -> str:
        return f"{self._prefix}:{account_id}:{day.day.isoformat()}:{day.timezone.key}"
