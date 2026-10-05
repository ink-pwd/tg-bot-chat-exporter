from sqlalchemy import delete, func, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.value_objects.telegram_session import TelegramSession
from infrastructure.persistence.models import TelegramSessionModel
from infrastructure.security.session_cipher import SessionCipher


class SqlTelegramSessionRepository:
    """Сессии хранятся только в зашифрованном виде."""

    def __init__(self, session_factory: async_sessionmaker, cipher: SessionCipher) -> None:
        self._session_factory = session_factory
        self._cipher = cipher

    async def save(self, account_id: int, session: TelegramSession) -> None:
        encrypted = self._cipher.encrypt(session.value)
        stmt = insert(TelegramSessionModel).values(
            account_id=account_id, encrypted_session=encrypted
        )
        stmt = stmt.on_duplicate_key_update(
            encrypted_session=stmt.inserted.encrypted_session, updated_at=func.now()
        )
        async with self._session_factory.begin() as db:
            await db.execute(stmt)

    async def get(self, account_id: int) -> TelegramSession | None:
        async with self._session_factory() as db:
            encrypted = await db.scalar(
                select(TelegramSessionModel.encrypted_session).where(
                    TelegramSessionModel.account_id == account_id
                )
            )
        if encrypted is None:
            return None
        return TelegramSession(self._cipher.decrypt(encrypted))

    async def delete(self, account_id: int) -> None:
        async with self._session_factory.begin() as db:
            await db.execute(
                delete(TelegramSessionModel).where(TelegramSessionModel.account_id == account_id)
            )
