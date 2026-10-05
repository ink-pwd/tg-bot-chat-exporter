from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from application.services.user_timezones import UserTimezones
from application.use_cases.configure_auto_export import ConfigureAutoExport
from domain.errors import AccountNotFound, AccountRevoked
from tests.unit.fakes import InMemoryAccounts, InMemoryBotUsers, InMemorySchedules

OWNER = 100
STRANGER = 200
KYIV = ZoneInfo("Europe/Kyiv")
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)  # 15:00 по Киеву


@pytest.fixture
def accounts():
    return InMemoryAccounts()


@pytest.fixture
def schedules(accounts):
    return InMemorySchedules(accounts)


@pytest.fixture
def users():
    return InMemoryBotUsers()


@pytest.fixture
def configure(accounts, schedules, users):
    return ConfigureAutoExport(accounts, schedules, UserTimezones(users, KYIV), lambda: NOW)


async def test_new_account_has_disabled_schedule(configure, accounts):
    account = accounts.add(OWNER, 1)

    schedule = await configure.get(OWNER, account.id)

    assert not schedule.enabled


async def test_enable(configure, accounts, schedules):
    account = accounts.add(OWNER, 1)

    schedule = await configure.set_time(OWNER, account.id, time(8, 0))

    assert schedule.enabled and schedule.local_time == time(8, 0)
    assert schedules.rows[account.id] == schedule
    # 08:00 сегодня уже прошло — первая автовыгрузка завтра
    assert schedule.last_run_day == date(2026, 10, 4)


async def test_disable(configure, accounts, schedules):
    account = accounts.add(OWNER, 1)
    await configure.set_time(OWNER, account.id, time(8, 0))

    schedule = await configure.disable(OWNER, account.id)

    assert not schedule.enabled
    assert not schedules.rows[account.id].enabled


async def test_foreign_account_schedule_is_not_accessible(configure, accounts, schedules):
    foreign = accounts.add(STRANGER, 2)

    with pytest.raises(AccountNotFound):
        await configure.get(OWNER, foreign.id)
    with pytest.raises(AccountNotFound):
        await configure.set_time(OWNER, foreign.id, time(8, 0))
    with pytest.raises(AccountNotFound):
        await configure.disable(OWNER, foreign.id)
    assert schedules.rows == {}


async def test_revoked_account_cannot_be_scheduled(configure, accounts):
    account = accounts.add(OWNER, 1)
    await accounts.mark_revoked(account.id, OWNER)

    with pytest.raises(AccountRevoked):
        await configure.set_time(OWNER, account.id, time(8, 0))


async def test_list_enabled_only_own(configure, accounts):
    mine = accounts.add(OWNER, 1)
    other_mine = accounts.add(OWNER, 2)
    foreign = accounts.add(STRANGER, 3)
    await configure.set_time(OWNER, mine.id, time(8, 0))
    await configure.set_time(OWNER, other_mine.id, time(9, 0))
    await configure.disable(OWNER, other_mine.id)
    await configure.set_time(STRANGER, foreign.id, time(7, 0))

    items = await configure.list_enabled(OWNER)

    assert [(a.id, s.local_time) for a, s in items] == [(mine.id, time(8, 0))]


async def test_time_is_interpreted_in_user_timezone(configure, accounts, users):
    users.timezones[OWNER] = "Asia/Tbilisi"  # 16:00 по Тбилиси
    account = accounts.add(OWNER, 1)

    schedule = await configure.set_time(OWNER, account.id, time(17, 0))

    # 17:00 по Тбилиси ещё не наступило — вчерашний день выгрузится сегодня
    assert schedule.last_run_day == date(2026, 10, 3)
