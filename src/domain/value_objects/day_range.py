from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class DayRange:
    """Календарный день в часовом поясе: [start, end).

    Длина не всегда 24 часа — в дни перехода на летнее/зимнее время 23 или 25.
    Границы отдаются в UTC: у datetime с одинаковым tzinfo Python вычитает
    и сравнивает «настенное» время, что в такие дни даёт неверный результат.
    """

    day: date
    timezone: ZoneInfo

    @property
    def start(self) -> datetime:
        return datetime.combine(self.day, time.min, tzinfo=self.timezone).astimezone(UTC)

    @property
    def end(self) -> datetime:
        return datetime.combine(
            self.day + timedelta(days=1), time.min, tzinfo=self.timezone
        ).astimezone(UTC)

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end

    @classmethod
    def today(cls, now: datetime, timezone: ZoneInfo) -> "DayRange":
        return cls(now.astimezone(timezone).date(), timezone)

    def is_finished(self, now: datetime) -> bool:
        return now >= self.end

    def is_future(self, now: datetime) -> bool:
        return now < self.start
