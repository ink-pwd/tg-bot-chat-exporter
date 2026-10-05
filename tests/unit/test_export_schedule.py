from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from domain.entities.export_schedule import ExportSchedule

KYIV = ZoneInfo("Europe/Kyiv")


def kyiv(day: int, hour: int, minute: int = 0, month: int = 10) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=KYIV).astimezone(UTC)


def schedule(at: time = time(8, 0), last_run_day: date | None = None, enabled: bool = True) -> ExportSchedule:
    return ExportSchedule(1, 100, at, enabled, last_run_day)


def test_before_time_nothing_is_due_if_previous_run_done():
    assert schedule(last_run_day=date(2026, 10, 3)).due_day(kyiv(5, 7, 59), KYIV) is None


def test_at_time_yesterday_is_due():
    assert schedule(last_run_day=date(2026, 10, 3)).due_day(kyiv(5, 8, 0), KYIV) == date(2026, 10, 4)


def test_already_done_today():
    assert schedule(last_run_day=date(2026, 10, 4)).due_day(kyiv(5, 15), KYIV) is None


def test_disabled_is_never_due():
    assert schedule(enabled=False).due_day(kyiv(5, 15), KYIV) is None


def test_missed_run_is_caught_up_once():
    # бот лежал вчера в 08:00 и запустился сегодня в 05:00: выгружаем позавчера
    assert schedule(last_run_day=date(2026, 10, 2)).due_day(kyiv(5, 5), KYIV) == date(2026, 10, 3)


def test_long_downtime_catches_up_only_latest_day():
    assert schedule(last_run_day=date(2026, 9, 1)).due_day(kyiv(5, 9), KYIV) == date(2026, 10, 4)


def test_time_is_in_owner_timezone():
    # 08:00 по Киеву = 06:00 по Лондону (UTC+1 в октябре)
    s = schedule(last_run_day=date(2026, 10, 3))
    now = kyiv(5, 7, 30)  # 05:30 Лондон

    assert s.due_day(now, KYIV) is None
    assert s.due_day(now, ZoneInfo("Europe/London")) is None
    assert s.due_day(kyiv(5, 10), ZoneInfo("Europe/London")) == date(2026, 10, 4)


def test_dst_change_day():
    # 25 октября переход на зимнее время; 08:00 наступает как обычно
    s = schedule(last_run_day=date(2026, 10, 24))

    assert s.due_day(kyiv(26, 8, 0), KYIV) == date(2026, 10, 25)


def test_enabling_skips_already_passed_occurrence():
    s = schedule(enabled=False).scheduled_at(time(8, 0), kyiv(5, 15), KYIV)

    assert s.enabled
    assert s.due_day(kyiv(5, 15), KYIV) is None  # не стартует сразу при включении
    assert s.due_day(kyiv(6, 8), KYIV) == date(2026, 10, 5)


def test_enabling_before_time_runs_today():
    s = schedule(enabled=False).scheduled_at(time(8, 0), kyiv(5, 7), KYIV)

    assert s.due_day(kyiv(5, 8), KYIV) == date(2026, 10, 4)


def test_moving_time_earlier_does_not_lose_yesterday():
    # было 20:00, в 10:00 поставили 08:00 — вчерашний день ещё не выгружен
    s = schedule(at=time(20, 0), last_run_day=date(2026, 10, 3))

    moved = s.scheduled_at(time(8, 0), kyiv(5, 10), KYIV)

    assert moved.due_day(kyiv(5, 10), KYIV) == date(2026, 10, 4)


def test_moving_time_later_does_not_repeat_done_day():
    s = schedule(at=time(8, 0), last_run_day=date(2026, 10, 4))

    moved = s.scheduled_at(time(20, 0), kyiv(5, 10), KYIV)

    assert moved.due_day(kyiv(5, 20), KYIV) is None
    assert moved.due_day(kyiv(6, 20), KYIV) == date(2026, 10, 5)
