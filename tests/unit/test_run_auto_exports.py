from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from application.dto.export import ExportSummary
from application.errors import ExportTooLarge, RecipientUnavailable, TelegramUnavailable, TooManyAttempts
from application.services.keyed_locks import KeyedLocks
from application.services.user_timezones import UserTimezones
from application.use_cases.export_daily_conversations import ExportDailyConversations
from application.use_cases.run_auto_exports import MAX_ATTEMPTS, RunAutoExports
from domain.entities.export_schedule import ExportSchedule
from domain.enums.account_status import AccountStatus
from domain.value_objects.telegram_session import TelegramSession
from tests.unit.export_fakes import FakeDelivery, FakeMessageGateway, InMemoryExportCache, conversation, message
from tests.unit.fakes import InMemoryAccounts, InMemoryBotUsers, InMemorySchedules, InMemorySessions

OWNER = 100
STRANGER = 200
KYIV = ZoneInfo("Europe/Kyiv")
YESTERDAY = date(2026, 10, 4)


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 5, 5, 0, tzinfo=UTC)  # 08:00 по Киеву

    def __call__(self) -> datetime:
        return self.now


@dataclass
class RecordingNotifier:
    completed_calls: list[tuple[int, ExportSummary]] = field(default_factory=list)
    revoked: list[tuple[int, int]] = field(default_factory=list)
    failures: list[tuple[int, int, date, Exception]] = field(default_factory=list)

    async def completed(self, user_id, summary):
        self.completed_calls.append((user_id, summary))

    async def account_revoked(self, user_id, account):
        self.revoked.append((user_id, account.id))

    async def failed(self, user_id, account, day, error):
        self.failures.append((user_id, account.id, day, error))


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def accounts():
    return InMemoryAccounts()


@pytest.fixture
def sessions():
    return InMemorySessions()


@pytest.fixture
def schedules(accounts):
    return InMemorySchedules(accounts)


@pytest.fixture
def gateway():
    return FakeMessageGateway(conversations=[conversation(message(1, datetime(2026, 10, 4, 9, tzinfo=UTC)))])


@pytest.fixture
def delivery():
    return FakeDelivery()


@pytest.fixture
def notifier():
    return RecordingNotifier()


@pytest.fixture
def users():
    return InMemoryBotUsers()


@pytest.fixture
def runner(accounts, sessions, schedules, gateway, delivery, notifier, users, clock):
    timezones = UserTimezones(users, KYIV)
    export = ExportDailyConversations(
        accounts, sessions, gateway, InMemoryExportCache(), delivery, KeyedLocks(), timezones, clock
    )
    return RunAutoExports(schedules, accounts, timezones, export, notifier, clock)


def add_scheduled(accounts, sessions, schedules, owner=OWNER, telegram_user_id=1, at=time(8, 0)):
    account = accounts.add(owner, telegram_user_id)
    sessions.rows[account.id] = TelegramSession(f"session-{account.id}")
    schedules.rows[account.id] = ExportSchedule(account.id, owner, at, True, date(2026, 10, 3))
    return account


async def test_due_schedule_exports_yesterday_and_marks_done(runner, accounts, sessions, schedules, gateway, delivery, notifier):
    account = add_scheduled(accounts, sessions, schedules)

    await runner.run_due()

    assert [day.day for _, day in gateway.calls] == [YESTERDAY]
    assert delivery.sent[0][0] == OWNER
    assert schedules.rows[account.id].last_run_day == YESTERDAY
    assert notifier.completed_calls[0][0] == OWNER


async def test_runs_once_per_day(runner, accounts, sessions, schedules, gateway, clock):
    add_scheduled(accounts, sessions, schedules)

    await runner.run_due()
    clock.now += timedelta(minutes=1)
    await runner.run_due()

    assert len(gateway.calls) == 1


async def test_not_due_before_time(runner, accounts, sessions, schedules, gateway):
    add_scheduled(accounts, sessions, schedules, at=time(9, 0))

    await runner.run_due()

    assert gateway.calls == []


async def test_file_goes_to_owner_of_each_account(runner, accounts, sessions, schedules, delivery):
    add_scheduled(accounts, sessions, schedules, owner=OWNER, telegram_user_id=1)
    add_scheduled(accounts, sessions, schedules, owner=STRANGER, telegram_user_id=2)

    await runner.run_due()

    recipients = sorted((user, export.account_id) for user, export in delivery.sent)
    assert recipients == [(OWNER, 1), (STRANGER, 2)]


async def test_uses_owner_timezone(runner, accounts, sessions, schedules, gateway, users):
    users.timezones[OWNER] = "Europe/London"  # сейчас 06:00 по Лондону
    add_scheduled(accounts, sessions, schedules)

    await runner.run_due()

    assert gateway.calls == []


async def test_revoked_session_disables_schedule_and_notifies(runner, accounts, sessions, schedules, gateway, notifier):
    from application.errors import SessionRevoked

    account = add_scheduled(accounts, sessions, schedules)
    gateway.error = SessionRevoked()

    await runner.run_due()

    assert not schedules.rows[account.id].enabled
    assert accounts.rows[account.id].status is AccountStatus.REVOKED
    assert notifier.revoked == [(OWNER, account.id)]


async def test_blocked_bot_disables_all_owner_schedules(runner, accounts, sessions, schedules, delivery):
    first = add_scheduled(accounts, sessions, schedules, telegram_user_id=1)
    second = add_scheduled(accounts, sessions, schedules, telegram_user_id=2, at=time(23, 0))
    foreign = add_scheduled(accounts, sessions, schedules, owner=STRANGER, telegram_user_id=3, at=time(23, 0))

    async def blocked(user_id, export):
        raise RecipientUnavailable()

    delivery.send = blocked

    await runner.run_due()

    assert not schedules.rows[first.id].enabled
    assert not schedules.rows[second.id].enabled
    assert schedules.rows[foreign.id].enabled


async def test_transient_failure_is_retried_later(runner, accounts, sessions, schedules, gateway, clock, notifier):
    account = add_scheduled(accounts, sessions, schedules)
    gateway.error = TelegramUnavailable()

    await runner.run_due()
    await runner.run_due()  # пауза ещё не прошла
    assert len(gateway.calls) == 1

    gateway.error = None
    clock.now += timedelta(minutes=5)
    await runner.run_due()

    assert len(gateway.calls) == 2
    assert schedules.rows[account.id].last_run_day == YESTERDAY
    assert notifier.failures == []


async def test_gives_up_after_max_attempts(runner, accounts, sessions, schedules, gateway, clock, notifier):
    account = add_scheduled(accounts, sessions, schedules)
    gateway.error = TelegramUnavailable()

    for _ in range(MAX_ATTEMPTS):
        await runner.run_due()
        clock.now += timedelta(minutes=5)
    await runner.run_due()

    assert len(gateway.calls) == MAX_ATTEMPTS
    assert schedules.rows[account.id].last_run_day == YESTERDAY
    assert schedules.rows[account.id].enabled
    assert [(u, a, d) for u, a, d, _ in notifier.failures] == [(OWNER, account.id, YESTERDAY)]


async def test_flood_wait_postpones_retry(runner, accounts, sessions, schedules, gateway, clock):
    add_scheduled(accounts, sessions, schedules)
    gateway.error = TooManyAttempts(1800)

    await runner.run_due()
    clock.now += timedelta(minutes=10)
    await runner.run_due()

    assert len(gateway.calls) == 1


async def test_too_large_is_reported_without_retries(runner, accounts, sessions, schedules, gateway, delivery, notifier):
    account = add_scheduled(accounts, sessions, schedules)

    async def too_large(user_id, export):
        raise ExportTooLarge()

    delivery.send = too_large

    await runner.run_due()

    assert schedules.rows[account.id].last_run_day == YESTERDAY
    assert len(notifier.failures) == 1


async def test_one_failure_does_not_block_others(runner, accounts, sessions, schedules, delivery, notifier):
    broken = add_scheduled(accounts, sessions, schedules, telegram_user_id=1)
    healthy = add_scheduled(accounts, sessions, schedules, owner=STRANGER, telegram_user_id=2)
    del sessions.rows[broken.id]  # сессии нет → аккаунт отозван

    await runner.run_due()

    assert schedules.rows[healthy.id].last_run_day == YESTERDAY
    assert notifier.revoked == [(OWNER, broken.id)]
