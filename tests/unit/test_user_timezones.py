from zoneinfo import ZoneInfo

import pytest

from application.services.user_timezones import UserTimezones, parse_timezone
from domain.errors import InvalidTimezone
from tests.unit.fakes import InMemoryBotUsers

DEFAULT = ZoneInfo("Europe/Kyiv")


async def test_default_when_not_set():
    assert await UserTimezones(InMemoryBotUsers(), DEFAULT).get(1) == DEFAULT


async def test_set_and_get():
    users = InMemoryBotUsers()
    timezones = UserTimezones(users, DEFAULT)

    await timezones.set(1, "europe/warsaw")

    assert users.timezones[1] == "Europe/Warsaw"
    assert (await timezones.get(1)).key == "Europe/Warsaw"
    assert await timezones.get(2) == DEFAULT


async def test_broken_stored_value_falls_back_to_default():
    users = InMemoryBotUsers()
    users.timezones[1] = "Not/AZone"

    assert await UserTimezones(users, DEFAULT).get(1) == DEFAULT


@pytest.mark.parametrize("name", ["", "Kyiv", "Mars/Base", "../etc/passwd", "/etc/localtime"])
def test_invalid_timezone(name):
    with pytest.raises(InvalidTimezone):
        parse_timezone(name)


@pytest.mark.parametrize(("name", "key"), [("UTC", "UTC"), (" utc ", "UTC"), ("America/New_York", "America/New_York")])
def test_valid_timezone(name, key):
    assert parse_timezone(name).key == key
