"""Сценарий: включить, изменить время или выключить ежедневную автовыгрузку пользователя."""
import logging
from collections.abc import Callable
from datetime import datetime, time

from application.ports.storage_repositories import ExportScheduleRepository
from application.services.user_timezones import UserTimezones
from domain.entities.export_schedule import ExportSchedule

logger = logging.getLogger(__name__)


class ConfigureAutoExport:
    """Включение, смена времени и выключение автовыгрузки своих бесед."""

    def __init__(
        self,
        schedules: ExportScheduleRepository,
        timezones: UserTimezones,
        clock: Callable[[], datetime],
    ) -> None:
        self._schedules = schedules
        self._timezones = timezones
        self._clock = clock

    async def get(self, user_id: int) -> ExportSchedule:
        return await self._schedules.get(user_id) or ExportSchedule.new(user_id)

    async def set_time(self, user_id: int, local_time: time) -> ExportSchedule:
        current = await self.get(user_id)
        timezone = await self._timezones.get(user_id)
        schedule = current.scheduled_at(local_time, self._clock(), timezone)
        await self._schedules.save(schedule)
        logger.info(
            "Auto export scheduled: user=%s time=%s tz=%s",
            user_id,
            local_time.strftime("%H:%M"),
            timezone.key,
        )
        return schedule

    async def disable(self, user_id: int) -> ExportSchedule:
        schedule = await self.get(user_id)
        if schedule.enabled:
            schedule = schedule.disabled()
            await self._schedules.save(schedule)
            logger.info("Auto export disabled: user=%s", user_id)
        return schedule
