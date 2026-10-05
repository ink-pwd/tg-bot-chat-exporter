from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from domain.value_objects.day_range import DayRange

KYIV = ZoneInfo("Europe/Kyiv")


def test_day_boundaries_in_timezone():
    day = DayRange(date(2026, 10, 5), KYIV)

    # Киев в октябре — UTC+3
    assert day.start == datetime(2026, 10, 4, 21, 0, tzinfo=UTC)
    assert day.end == datetime(2026, 10, 5, 21, 0, tzinfo=UTC)


def test_contains_is_half_open():
    day = DayRange(date(2026, 10, 5), KYIV)

    assert day.contains(datetime(2026, 10, 4, 21, 0, tzinfo=UTC))
    assert day.contains(datetime(2026, 10, 5, 20, 59, 59, tzinfo=UTC))
    assert not day.contains(datetime(2026, 10, 5, 21, 0, tzinfo=UTC))
    assert not day.contains(datetime(2026, 10, 4, 20, 59, 59, tzinfo=UTC))


def test_dst_end_day_is_25_hours():
    # 25 октября 2026 Украина переходит на зимнее время
    day = DayRange(date(2026, 10, 25), KYIV)

    assert day.end - day.start == timedelta(hours=25)


def test_dst_start_day_is_23_hours():
    day = DayRange(date(2026, 3, 29), KYIV)

    assert day.end - day.start == timedelta(hours=23)


def test_today_depends_on_timezone():
    late_evening_utc = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)

    assert DayRange.today(late_evening_utc, KYIV).day == date(2026, 10, 6)
    assert DayRange.today(late_evening_utc, ZoneInfo("UTC")).day == date(2026, 10, 5)


def test_finished_and_future():
    day = DayRange(date(2026, 10, 5), KYIV)

    assert day.is_future(datetime(2026, 10, 4, 20, 0, tzinfo=UTC))
    assert not day.is_finished(datetime(2026, 10, 5, 20, 0, tzinfo=UTC))
    assert day.is_finished(datetime(2026, 10, 5, 21, 0, tzinfo=UTC))
