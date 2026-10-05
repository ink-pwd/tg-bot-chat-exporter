from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.models import BotUserModel


class SqlBotUserRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def ensure_exists(self, user_id: int) -> None:
        async with self._session_factory.begin() as db:
            await db.execute(insert(BotUserModel).values(id=user_id).prefix_with("IGNORE"))

    async def get_timezone(self, user_id: int) -> str | None:
        async with self._session_factory() as db:
            return await db.scalar(select(BotUserModel.timezone).where(BotUserModel.id == user_id))

    async def set_timezone(self, user_id: int, timezone: str) -> None:
        stmt = insert(BotUserModel).values(id=user_id, timezone=timezone)
        stmt = stmt.on_duplicate_key_update(timezone=stmt.inserted.timezone)
        async with self._session_factory.begin() as db:
            await db.execute(stmt)
