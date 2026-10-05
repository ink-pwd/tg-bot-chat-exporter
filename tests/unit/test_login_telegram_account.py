import pytest

from application.dto.login import (
    LoginCompleted,
    LoginTimedOut,
    PasswordRequired,
    QrRefreshed,
)
from application.use_cases.login_telegram_account import LoginTelegramAccount
from domain.errors import AccountOwnedByAnotherUser, InvalidPhoneNumber
from domain.value_objects.telegram_session import TelegramSession
from tests.unit.fakes import (
    FakeAuthGateway,
    InMemoryAccounts,
    InMemoryBotUsers,
    InMemorySessions,
    authorized,
)

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
def users() -> InMemoryBotUsers:
    return InMemoryBotUsers()


@pytest.fixture
def login(gateway, users, accounts, sessions) -> LoginTelegramAccount:
    return LoginTelegramAccount(gateway, users, accounts, sessions)


async def test_code_login_saves_account_for_requester(login, gateway, users, accounts, sessions):
    gateway.sign_in_outcome = authorized(telegram_user_id=555, session="s1")

    result = await login.submit_code(OWNER, "12345")

    assert isinstance(result, LoginCompleted)
    assert result.account.owner_id == OWNER
    assert result.account.telegram_user_id == 555
    assert OWNER in users.ids
    assert sessions.rows[result.account.id] == TelegramSession("s1")


async def test_password_required_is_passed_through(login, gateway, sessions):
    gateway.sign_in_outcome = PasswordRequired()

    assert isinstance(await login.submit_code(OWNER, "12345"), PasswordRequired)
    assert sessions.rows == {}


async def test_password_completes_login(login, gateway):
    gateway.sign_in_outcome = authorized(telegram_user_id=555)

    result = await login.submit_password(OWNER, "secret")

    assert isinstance(result, LoginCompleted)


async def test_relogin_by_same_owner_updates_session(login, gateway, accounts, sessions):
    gateway.sign_in_outcome = authorized(telegram_user_id=555, session="old")
    first = await login.submit_code(OWNER, "1")
    gateway.sign_in_outcome = authorized(telegram_user_id=555, session="new", name="Renamed")

    second = await login.submit_code(OWNER, "2")

    assert second.account.id == first.account.id
    assert second.account.display_name == "Renamed"
    assert len(accounts.rows) == 1
    assert sessions.rows[first.account.id] == TelegramSession("new")


async def test_account_owned_by_another_user_is_rejected(login, gateway, accounts, sessions):
    existing = accounts.add(owner_id=OWNER, telegram_user_id=555)
    sessions.rows[existing.id] = TelegramSession("owner-session")
    gateway.sign_in_outcome = authorized(telegram_user_id=555, session="stranger-session")

    with pytest.raises(AccountOwnedByAnotherUser):
        await login.submit_code(STRANGER, "12345")

    # аккаунт и сессия владельца не тронуты, новая сессия завершена в Telegram
    assert accounts.rows[existing.id].owner_id == OWNER
    assert sessions.rows == {existing.id: TelegramSession("owner-session")}
    assert gateway.logged_out == [TelegramSession("stranger-session")]
    assert await accounts.list_owned(STRANGER) == []


async def test_qr_login_completes(login, gateway):
    gateway.qr_outcome = authorized(telegram_user_id=777)

    result = await login.wait_qr(OWNER)

    assert isinstance(result, LoginCompleted)
    assert result.account.owner_id == OWNER


@pytest.mark.parametrize("outcome", [QrRefreshed("tg://login?token=new"), LoginTimedOut(), PasswordRequired()])
async def test_qr_intermediate_outcomes_are_passed_through(login, gateway, sessions, outcome):
    gateway.qr_outcome = outcome

    assert await login.wait_qr(OWNER) == outcome
    assert sessions.rows == {}


async def test_phone_is_normalized_before_sending(login, gateway):
    await login.start_phone(OWNER, " +380 (50) 123-45-67 ")

    assert [p.value for p in gateway.started_phones] == ["+380501234567"]


async def test_invalid_phone_is_rejected_without_calling_telegram(login, gateway):
    with pytest.raises(InvalidPhoneNumber):
        await login.start_phone(OWNER, "not a phone")

    assert gateway.started_phones == []
