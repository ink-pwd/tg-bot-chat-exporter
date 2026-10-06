"""Блокировки по ключу: одинаковые выгрузки не выполняются параллельно, вторая ждёт первую."""
import asyncio
from collections.abc import AsyncIterator, Hashable
from contextlib import asynccontextmanager


class KeyedLocks:
    """Отдельный asyncio.Lock на каждый ключ; неиспользуемые блокировки удаляются.

    Работает в пределах одного процесса — бот запускается в одном экземпляре.
    """

    def __init__(self) -> None:
        self._locks: dict[Hashable, asyncio.Lock] = {}
        self._holders: dict[Hashable, int] = {}

    @asynccontextmanager
    async def hold(self, key: Hashable) -> AsyncIterator[None]:
        lock = self._locks.setdefault(key, asyncio.Lock())
        self._holders[key] = self._holders.get(key, 0) + 1
        try:
            async with lock:
                yield
        finally:
            self._holders[key] -= 1
            if self._holders[key] == 0:
                del self._holders[key]
                del self._locks[key]
