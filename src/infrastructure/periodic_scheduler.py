"""Запуск задачи каждые N секунд: сбой одного прохода не останавливает цикл."""
import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


async def run_periodically(job: Callable[[], Awaitable[None]], interval_seconds: float) -> None:
    """Запускает job каждые interval_seconds; сбой одного прохода не останавливает цикл."""
    while True:
        try:
            await job()
        except Exception:
            logger.exception("Scheduled job failed")
        await asyncio.sleep(interval_seconds)
