import asyncio
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from application.dto.export import CachedExport
from application.errors import SessionRevoked
from application.services.keyed_locks import KeyedLocks
from application.services.user_timezones import UserTimezones
from application.use_cases.export_daily_conversations import (
    CURRENT_DAY_TTL,
    FINISHED_DAY_TTL,
    ExportDailyConversations,
)
from domain.enums.account_status import AccountStatus
from domain.errors import AccountNotFound, AccountRevoked, InvalidExportDay
from domain.value_objects.day_range import DayRange
from domain.value_objects.telegram_session import TelegramSession
from tests.unit.export_fakes import (
    FakeDelivery,
    FakeMessageGateway,
    InMemoryExportCache,
    conversation,
    message,
)
from tests.unit.fakes import InMemoryAccounts, InMemoryBotUsers, InMemorySessions

OWNER = 100
STRANGER = 200
KYIV = ZoneInfo("Europe/Kyiv")
# 2026-10-05 15:00 по Киеву
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
TODAY = date(2026, 10, 5)
YESTERDAY = date(2026, 10, 4)


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def accounts():
    return InMemoryAccounts()


@pytest.fixture
def sessions():
    return InMemorySessions()


@pytest.fixture
def gateway():
    return FakeMessageGateway(
        conversations=[conversation(message(1, datetime(2026, 10, 4, 9, 0, tzinfo=UTC)))]
    )


@pytest.fixture
def cache():
    return InMemoryExportCache()


@pytest.fixture
def delivery():
    return FakeDelivery()


@pytest.fixture
def clock():
    return Clock(NOW)


@pytest.fixture
def users():
    return InMemoryBotUsers()


@pytest.fixture
def export(accounts, sessions, gateway, cache, delivery, clock, users):
    return ExportDailyConversations(
        accounts, sessions, gateway, cache, delivery, KeyedLocks(), UserTimezones(users, KYIV), clock
    )


@pytest.fixture
def account(accounts, sessions):
    account = accounts.add(owner_id=OWNER, telegram_user_id=555)
    sessions.rows[account.id] = TelegramSession("owner-session")
    return account


def cached(file_id: str | None = "file-cached", exported_at: datetime = NOW) -> CachedExport:
    return CachedExport(file_id, conversations_count=2, messages_count=7, exported_at=exported_at)


# --- изоляция -----------------------------------------------------------------


async def test_foreign_account_cannot_be_exported(export, accounts, sessions, gateway, cache, delivery):
    foreign = accounts.add(owner_id=STRANGER, telegram_user_id=777)
    sessions.rows[foreign.id] = TelegramSession("foreign-session")

    with pytest.raises(AccountNotFound):
        await export.execute(OWNER, foreign.id, YESTERDAY)

    assert gateway.calls == []
    assert delivery.sent == [] and delivery.resent == []


async def test_foreign_cached_export_is_not_served(export, accounts, cache, delivery):
    foreign = accounts.add(owner_id=STRANGER, telegram_user_id=777)
    await cache.put(foreign.id, DayRange(YESTERDAY, KYIV), cached("foreign-file"), FINISHED_DAY_TTL)
    cache.reads.clear()

    with pytest.raises(AccountNotFound):
        await export.execute(OWNER, foreign.id, YESTERDAY)

    # кеш чужого аккаунта даже не читается
    assert cache.reads == []
    assert delivery.resent == []


async def test_missing_account(export):
    with pytest.raises(AccountNotFound):
        await export.execute(OWNER, 9999, YESTERDAY)


# --- выгрузка -------------------------------------------------------------------


async def test_export_fetches_sends_and_caches(export, account, gateway, cache, delivery):
    summary = await export.execute(OWNER, account.id, YESTERDAY)

    session, day = gateway.calls[0]
    assert session == TelegramSession("owner-session")
    assert day == DayRange(YESTERDAY, KYIV)
    assert [user for user, _ in delivery.sent] == [OWNER]
    assert summary.messages_count == 1
    assert summary.conversations_count == 1
    assert summary.from_cache is False
    assert cache.rows[(account.id, "2026-10-04", "Europe/Kyiv")].file_id == "file-1"


async def test_finished_day_is_cached_for_a_day(export, account, cache):
    await export.execute(OWNER, account.id, YESTERDAY)

    assert cache.ttls[(account.id, "2026-10-04", "Europe/Kyiv")] == FINISHED_DAY_TTL


async def test_current_day_is_cached_briefly(export, account, cache):
    await export.execute(OWNER, account.id, TODAY)

    assert cache.ttls[(account.id, "2026-10-05", "Europe/Kyiv")] == CURRENT_DAY_TTL


async def test_future_day_is_rejected(export, account, gateway):
    with pytest.raises(InvalidExportDay):
        await export.execute(OWNER, account.id, TODAY + timedelta(days=1))

    assert gateway.calls == []


async def test_today_uses_default_timezone(export, clock):
    # 22:30 UTC 5 октября — это уже 6 октября по Киеву
    clock.now = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)

    assert await export.today(OWNER) == date(2026, 10, 6)


async def test_today_uses_user_timezone(export, clock, users):
    clock.now = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)
    users.timezones[OWNER] = "Europe/London"  # 23:30 по Лондону — ещё 5 октября

    assert await export.today(OWNER) == date(2026, 10, 5)


async def test_day_boundaries_follow_user_timezone(export, account, gateway, users):
    users.timezones[OWNER] = "America/New_York"

    await export.execute(OWNER, account.id, YESTERDAY)

    _, day = gateway.calls[0]
    assert day.timezone.key == "America/New_York"


async def test_empty_day_sends_no_file(export, account, gateway, cache, delivery):
    gateway.conversations = []

    summary = await export.execute(OWNER, account.id, YESTERDAY)

    assert summary.messages_count == 0
    assert delivery.sent == []
    assert cache.rows[(account.id, "2026-10-04", "Europe/Kyiv")].file_id is None


# --- кеш ------------------------------------------------------------------------


async def test_cached_export_is_resent_without_telegram(export, account, gateway, cache, delivery):
    await cache.put(account.id, DayRange(YESTERDAY, KYIV), cached(), FINISHED_DAY_TTL)

    summary = await export.execute(OWNER, account.id, YESTERDAY)

    assert gateway.calls == []
    assert delivery.resent == [(OWNER, "file-cached")]
    assert summary.from_cache is True
    assert summary.messages_count == 7


async def test_cached_empty_day_is_served_without_file(export, account, gateway, cache, delivery):
    await cache.put(account.id, DayRange(YESTERDAY, KYIV), cached(file_id=None), FINISHED_DAY_TTL)

    summary = await export.execute(OWNER, account.id, YESTERDAY)

    assert summary.from_cache is True
    assert gateway.calls == [] and delivery.resent == []


async def test_stale_file_id_triggers_fresh_export(export, account, gateway, cache, delivery):
    await cache.put(account.id, DayRange(YESTERDAY, KYIV), cached("stale"), FINISHED_DAY_TTL)
    delivery.stale_file_ids.add("stale")

    summary = await export.execute(OWNER, account.id, YESTERDAY)

    assert summary.from_cache is False
    assert len(gateway.calls) == 1
    assert cache.rows[(account.id, "2026-10-04", "Europe/Kyiv")].file_id == "file-1"


async def test_refresh_ignores_cache(export, account, gateway, cache, clock):
    await cache.put(
        account.id, DayRange(TODAY, KYIV), cached(exported_at=NOW - timedelta(minutes=5)), CURRENT_DAY_TTL
    )

    summary = await export.execute(OWNER, account.id, TODAY, refresh=True)

    assert summary.from_cache is False
    assert len(gateway.calls) == 1


async def test_concurrent_requests_fetch_once(export, account, gateway, delivery):
    gateway.delay = 0.05

    first, second = await asyncio.gather(
        export.execute(OWNER, account.id, YESTERDAY),
        export.execute(OWNER, account.id, YESTERDAY),
    )

    assert len(gateway.calls) == 1
    assert {first.from_cache, second.from_cache} == {False, True}
    assert len(delivery.sent) == 1 and len(delivery.resent) == 1


async def test_concurrent_refreshes_fetch_once(export, account, gateway):
    gateway.delay = 0.05

    await asyncio.gather(
        export.execute(OWNER, account.id, TODAY, refresh=True),
        export.execute(OWNER, account.id, TODAY, refresh=True),
    )

    assert len(gateway.calls) == 1


# --- отозванная сессия ----------------------------------------------------------


async def test_revoked_session_marks_account(export, account, accounts, sessions, gateway):
    gateway.error = SessionRevoked()

    with pytest.raises(AccountRevoked):
        await export.execute(OWNER, account.id, YESTERDAY)

    assert accounts.rows[account.id].status is AccountStatus.REVOKED
    assert account.id not in sessions.rows


async def test_revoked_account_is_not_exported(export, account, accounts, gateway):
    await accounts.mark_revoked(account.id, OWNER)

    with pytest.raises(AccountRevoked):
        await export.execute(OWNER, account.id, YESTERDAY)

    assert gateway.calls == []


async def test_missing_session_marks_account_revoked(export, account, accounts, sessions, gateway):
    del sessions.rows[account.id]

    with pytest.raises(AccountRevoked):
        await export.execute(OWNER, account.id, YESTERDAY)

    assert accounts.rows[account.id].status is AccountStatus.REVOKED
    assert gateway.calls == []


async def test_check_access(export, account, accounts):
    foreign = accounts.add(owner_id=STRANGER, telegram_user_id=777)

    assert await export.check_access(OWNER, account.id) == account
    with pytest.raises(AccountNotFound):
        await export.check_access(OWNER, foreign.id)
