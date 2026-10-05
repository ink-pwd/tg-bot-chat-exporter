from datetime import date, time

import pytest

from domain.entities.export_schedule import ExportSchedule
from domain.value_objects.telegram_profile import TelegramProfile
from infrastructure.persistence.repositories.bot_user_repository import SqlBotUserRepository
from infrastructure.persistence.repositories.export_schedule_repository import (
    SqlExportScheduleRepository,
)
from infrastructure.persistence.repositories.telegram_account_repository import (
    SqlTelegramAccountRepository,
)

pytestmark = pytest.mark.integration

OWNER = 100
STRANGER = 200


@pytest.fixture
async def users(session_factory):
    repo = SqlBotUserRepository(session_factory)
    await repo.ensure_exists(OWNER)
    await repo.ensure_exists(STRANGER)
    return repo


@pytest.fixture
def accounts(session_factory, users):
    return SqlTelegramAccountRepository(session_factory)


@pytest.fixture
def schedules(session_factory):
    return SqlExportScheduleRepository(session_factory)


async def add_account(accounts, owner: int, telegram_user_id: int):
    return await accounts.save_authorized(owner, TelegramProfile(telegram_user_id, "Acc", None))


def schedule(account_id: int, owner: int, at: time = time(8, 30), enabled: bool = True) -> ExportSchedule:
    return ExportSchedule(account_id, owner, at, enabled, date(2026, 10, 4))


async def test_timezone_roundtrip(users):
    assert await users.get_timezone(OWNER) is None

    await users.set_timezone(OWNER, "Europe/Warsaw")

    assert await users.get_timezone(OWNER) == "Europe/Warsaw"


async def test_set_timezone_creates_user(users):
    await users.set_timezone(300, "UTC")

    assert await users.get_timezone(300) == "UTC"


async def test_schedule_roundtrip(accounts, schedules):
    account = await add_account(accounts, OWNER, 1)

    await schedules.save(schedule(account.id, OWNER))

    assert await schedules.get_owned(account.id, OWNER) == schedule(account.id, OWNER)


async def test_schedule_is_not_visible_to_stranger(accounts, schedules):
    account = await add_account(accounts, OWNER, 1)
    await schedules.save(schedule(account.id, OWNER))

    assert await schedules.get_owned(account.id, STRANGER) is None
    assert await schedules.list_owned(STRANGER) == []


async def test_stranger_cannot_save_schedule_for_foreign_account(accounts, schedules):
    account = await add_account(accounts, OWNER, 1)

    await schedules.save(schedule(account.id, STRANGER))

    assert await schedules.list_enabled() == []


async def test_update_schedule(accounts, schedules):
    account = await add_account(accounts, OWNER, 1)
    await schedules.save(schedule(account.id, OWNER))

    await schedules.save(schedule(account.id, OWNER, at=time(23, 45), enabled=False))

    saved = await schedules.get_owned(account.id, OWNER)
    assert (saved.local_time, saved.enabled) == (time(23, 45), False)


async def test_list_enabled_with_owners(accounts, schedules):
    mine = await add_account(accounts, OWNER, 1)
    foreign = await add_account(accounts, STRANGER, 2)
    off = await add_account(accounts, OWNER, 3)
    await schedules.save(schedule(mine.id, OWNER))
    await schedules.save(schedule(foreign.id, STRANGER))
    await schedules.save(schedule(off.id, OWNER, enabled=False))

    enabled = await schedules.list_enabled()

    assert sorted((s.account_id, s.owner_id) for s in enabled) == [(mine.id, OWNER), (foreign.id, STRANGER)]


async def test_mark_done_and_disable(accounts, schedules):
    account = await add_account(accounts, OWNER, 1)
    await schedules.save(schedule(account.id, OWNER))

    await schedules.mark_done(account.id, date(2026, 10, 5))
    await schedules.disable(account.id)

    saved = await schedules.get_owned(account.id, OWNER)
    assert saved.last_run_day == date(2026, 10, 5)
    assert not saved.enabled


async def test_disable_all_owned(accounts, schedules):
    first = await add_account(accounts, OWNER, 1)
    second = await add_account(accounts, OWNER, 2)
    foreign = await add_account(accounts, STRANGER, 3)
    for account, owner in ((first, OWNER), (second, OWNER), (foreign, STRANGER)):
        await schedules.save(schedule(account.id, owner))

    await schedules.disable_all_owned(OWNER)

    assert [s.account_id for s in await schedules.list_enabled()] == [foreign.id]


async def test_schedule_is_deleted_with_account(accounts, schedules):
    account = await add_account(accounts, OWNER, 1)
    await schedules.save(schedule(account.id, OWNER))

    await accounts.delete_owned(account.id, OWNER)

    assert await schedules.list_enabled() == []
