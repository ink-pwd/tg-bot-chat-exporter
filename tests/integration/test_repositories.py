import pytest
from sqlalchemy import select

from domain.enums.account_status import AccountStatus
from domain.errors import AccountOwnedByAnotherUser
from domain.value_objects.telegram_profile import TelegramProfile
from domain.value_objects.telegram_session import TelegramSession
from infrastructure.persistence.models import TelegramAccountModel, TelegramSessionModel
from infrastructure.persistence.repositories.bot_user_repository import SqlBotUserRepository
from infrastructure.persistence.repositories.telegram_account_repository import (
    SqlTelegramAccountRepository,
)
from infrastructure.persistence.repositories.telegram_session_repository import (
    SqlTelegramSessionRepository,
)
from infrastructure.security.session_cipher import SessionCipher

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
def sessions(session_factory):
    return SqlTelegramSessionRepository(session_factory, SessionCipher((SessionCipher.generate_key(),)))


def profile(telegram_user_id: int = 555, name: str = "Поддержка 🛟") -> TelegramProfile:
    return TelegramProfile(telegram_user_id, name, "support")


async def test_ensure_exists_is_idempotent(users):
    await users.ensure_exists(OWNER)


async def test_save_authorized_creates_account(accounts):
    account = await accounts.save_authorized(OWNER, profile())

    assert account.owner_id == OWNER
    assert account.display_name == "Поддержка 🛟"
    assert account.status is AccountStatus.ACTIVE
    assert await accounts.get_owned(account.id, OWNER) == account


async def test_accounts_are_isolated_by_owner(accounts):
    mine = await accounts.save_authorized(OWNER, profile(1))
    foreign = await accounts.save_authorized(STRANGER, profile(2))

    assert await accounts.list_owned(OWNER) == [mine]
    assert await accounts.get_owned(foreign.id, OWNER) is None


async def test_same_owner_relogin_updates_profile(accounts):
    first = await accounts.save_authorized(OWNER, profile(name="Old"))

    second = await accounts.save_authorized(OWNER, profile(name="New"))

    assert second.id == first.id
    assert second.display_name == "New"


async def test_foreign_owner_cannot_take_over_account(accounts):
    mine = await accounts.save_authorized(OWNER, profile())

    with pytest.raises(AccountOwnedByAnotherUser):
        await accounts.save_authorized(STRANGER, profile(name="Hijacked"))

    assert await accounts.get_owned(mine.id, OWNER) == mine
    assert await accounts.list_owned(STRANGER) == []


async def test_delete_owned_ignores_foreign_owner(accounts):
    mine = await accounts.save_authorized(OWNER, profile())

    await accounts.delete_owned(mine.id, STRANGER)
    assert await accounts.get_owned(mine.id, OWNER) == mine

    await accounts.delete_owned(mine.id, OWNER)
    assert await accounts.get_owned(mine.id, OWNER) is None


async def test_session_is_stored_encrypted(session_factory, accounts, sessions):
    account = await accounts.save_authorized(OWNER, profile())

    await sessions.save(account.id, TelegramSession("plain-session-string"))

    async with session_factory() as db:
        raw = await db.scalar(select(TelegramSessionModel.encrypted_session))
    assert b"plain-session-string" not in raw
    assert await sessions.get(account.id) == TelegramSession("plain-session-string")


async def test_session_save_overwrites(accounts, sessions):
    account = await accounts.save_authorized(OWNER, profile())

    await sessions.save(account.id, TelegramSession("old"))
    await sessions.save(account.id, TelegramSession("new"))

    assert await sessions.get(account.id) == TelegramSession("new")


async def test_deleting_account_deletes_session(session_factory, accounts, sessions):
    account = await accounts.save_authorized(OWNER, profile())
    await sessions.save(account.id, TelegramSession("s"))

    await accounts.delete_owned(account.id, OWNER)

    assert await sessions.get(account.id) is None
    async with session_factory() as db:
        assert await db.scalar(select(TelegramAccountModel)) is None
