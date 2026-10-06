"""Расписание автовыгрузки и правила, за какой день и когда она должна сработать."""
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class ExportSchedule:
    """Ежедневная автовыгрузка закончившегося дня в local_time по поясу владельца."""

    owner_id: int
    local_time: time
    enabled: bool
    last_run_day: date | None  # за какой день автовыгрузка уже выполнена

    def latest_due_day(self, now: datetime, timezone: ZoneInfo) -> date:
        """День, который должна была выгрузить последняя наступившая автовыгрузка.

        В 08:00 выгружается вчерашний день. До 08:00 последней была вчерашняя
        автовыгрузка — она отвечала за позавчера.
        """
        local_now = now.astimezone(timezone)
        days_back = 1 if local_now.time() >= self.local_time else 2
        return local_now.date() - timedelta(days=days_back)

    def due_day(self, now: datetime, timezone: ZoneInfo) -> date | None:
        """День для выгрузки прямо сейчас или None.

        Если бот был выключен в нужное время, пропущенный день выгружается после
        запуска — но только последний, без лавины за все дни простоя.
        """
        if not self.enabled:
            return None
        day = self.latest_due_day(now, timezone)
        if self.last_run_day is not None and self.last_run_day >= day:
            return None
        return day

    def scheduled_at(self, local_time: time, now: datetime, timezone: ZoneInfo) -> "ExportSchedule":
        """Включает автовыгрузку или меняет её время.

        При включении уже прошедшие наступления считаются выполненными — иначе
        включение в 15:00 со временем 08:00 тут же запустило бы выгрузку.
        При смене времени у включённой автовыгрузки ничего не пропускается:
        если новое время сегодня уже прошло, а вчерашний день не выгружен,
        он выгрузится сразу.
        """
        updated = replace(self, local_time=local_time, enabled=True)
        if self.enabled:
            return updated
        skip_until = updated.latest_due_day(now, timezone)
        return replace(updated, last_run_day=max(skip_until, self.last_run_day or date.min))

    def disabled(self) -> "ExportSchedule":
        return replace(self, enabled=False)

    @classmethod
    def new(cls, owner_id: int) -> "ExportSchedule":
        return cls(owner_id, time(8, 0), enabled=False, last_run_day=None)
