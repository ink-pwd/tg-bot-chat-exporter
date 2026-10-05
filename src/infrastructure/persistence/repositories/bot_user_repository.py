from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.models import BotUserModel


class SqlBotUserRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def ensure_exists(self, user_id: int) -> None:
        async with self._session_factory.begin() as db:
            await db.execute(insert(BotUserModel).values(id=user_id).prefix_with("IGNORE"))
