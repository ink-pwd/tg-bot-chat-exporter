import pytest

from application.use_cases.manage_telegram_accounts import ManageTelegramAccounts
from domain.errors import AccountNotFound
from domain.value_objects.telegram_session import TelegramSession
from tests.unit.fakes import FakeAuthGateway, InMemoryAccounts, InMemorySessions

OWNER = 100
STRANGER = 200


@pytest.fixture
def gateway() -> FakeAuthGateway:
    return FakeAuthGateway()


@pytest.fixture
def accounts() -> InMemoryAccounts:
    return InMemoryAccounts()


@pytest.fixture
def sessions() -> InMemorySessions:
    return InMemorySessions()


@pytest.fixture
def manage(gateway, accounts, sessions) -> ManageTelegramAccounts:
    return ManageTelegramAccounts(gateway, accounts, sessions)


async def test_list_returns_only_own_accounts(manage, accounts):
    mine = accounts.add(owner_id=OWNER, telegram_user_id=1)
    accounts.add(owner_id=STRANGER, telegram_user_id=2)

    assert await manage.list(OWNER) == [mine]


async def test_get_own_account(manage, accounts):
    mine = accounts.add(owner_id=OWNER, telegram_user_id=1)

    assert await manage.get(OWNER, mine.id) == mine


async def test_get_foreign_account_looks_like_missing(manage, accounts):
    foreign = accounts.add(owner_id=STRANGER, telegram_user_id=2)

    with pytest.raises(AccountNotFound):
        await manage.get(OWNER, foreign.id)
    with pytest.raises(AccountNotFound):
        await manage.get(OWNER, 9999)


async def test_log_out_foreign_account_changes_nothing(manage, gateway, accounts, sessions):
    foreign = accounts.add(owner_id=STRANGER, telegram_user_id=2)
    sessions.rows[foreign.id] = TelegramSession("foreign")

    with pytest.raises(AccountNotFound):
        await manage.log_out(OWNER, foreign.id)

    assert foreign.id in accounts.rows
    assert foreign.id in sessions.rows
    assert gateway.logged_out == []


async def test_log_out_own_account(manage, gateway, accounts, sessions):
    mine = accounts.add(owner_id=OWNER, telegram_user_id=1)
    sessions.rows[mine.id] = TelegramSession("mine")

    await manage.log_out(OWNER, mine.id)

    assert gateway.logged_out == [TelegramSession("mine")]
    assert mine.id not in accounts.rows
    assert mine.id not in sessions.rows


async def test_log_out_removes_account_even_if_telegram_fails(manage, gateway, accounts, sessions):
    mine = accounts.add(owner_id=OWNER, telegram_user_id=1)
    sessions.rows[mine.id] = TelegramSession("mine")
    gateway.fail_log_out = True

    await manage.log_out(OWNER, mine.id)

    assert mine.id not in accounts.rows
    assert mine.id not in sessions.rows
