import json

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.support_chat import SupportChat
from domain.enums.chat_type import ChatType
from infrastructure.persistence.models import SupportChatModel


class SqlSupportChatRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def list_owned(self, owner_id: int) -> list[SupportChat]:
        async with self._session_factory() as db:
            rows = await db.scalars(
                select(SupportChatModel)
                .where(SupportChatModel.owner_id == owner_id)
                .order_by(SupportChatModel.active.desc(), SupportChatModel.title)
            )
            return [_to_entity(row) for row in rows]

    async def get_owned(self, chat_id: int, owner_id: int) -> SupportChat | None:
        async with self._session_factory() as db:
            row = await db.scalar(
                select(SupportChatModel).where(
                    SupportChatModel.id == chat_id, SupportChatModel.owner_id == owner_id
                )
            )
            return _to_entity(row) if row else None

    async def find_active(self, telegram_chat_id: int) -> SupportChat | None:
        async with self._session_factory() as db:
            row = await db.scalar(
                select(SupportChatModel).where(
                    SupportChatModel.telegram_chat_id == telegram_chat_id,
                    SupportChatModel.active.is_(True),
                )
            )
            return _to_entity(row) if row else None

    async def connect(
        self, telegram_chat_id: int, owner_id: int, title: str, chat_type: ChatType
    ) -> SupportChat:
        async with self._session_factory.begin() as db:
            row = await db.scalar(
                select(SupportChatModel)
                .where(SupportChatModel.telegram_chat_id == telegram_chat_id)
                .with_for_update()
            )
            if row is not None and row.owner_id != owner_id:
                # беседу подключил другой человек: история прежнего владельца ему не достаётся
                await db.delete(row)
                await db.flush()
                row = None
            if row is None:
                row = SupportChatModel(telegram_chat_id=telegram_chat_id, owner_id=owner_id)
                db.add(row)
            row.title = title[:255]
            row.chat_type = chat_type.value
            row.active = True
            await db.flush()
            return _to_entity(row)

    async def deactivate(self, telegram_chat_id: int) -> None:
        await self._update(SupportChatModel.telegram_chat_id == telegram_chat_id, active=False)

    async def migrate(self, old_telegram_chat_id: int, new_telegram_chat_id: int) -> None:
        async with self._session_factory.begin() as db:
            # Telegram присылает событие и в старую, и в новую беседу — второе ничего не меняет
            if await db.scalar(
                select(SupportChatModel.id).where(
                    SupportChatModel.telegram_chat_id == new_telegram_chat_id
                )
            ):
                return
            await db.execute(
                update(SupportChatModel)
                .where(SupportChatModel.telegram_chat_id == old_telegram_chat_id)
                .values(telegram_chat_id=new_telegram_chat_id, chat_type=ChatType.SUPERGROUP.value)
            )

    async def rename(self, telegram_chat_id: int, title: str) -> None:
        await self._update(SupportChatModel.telegram_chat_id == telegram_chat_id, title=title[:255])

    async def save_admin_ids(self, chat_id: int, admin_ids: frozenset[int]) -> None:
        await self._update(SupportChatModel.id == chat_id, admin_ids=json.dumps(sorted(admin_ids)))

    async def delete_owned(self, chat_id: int, owner_id: int) -> None:
        async with self._session_factory.begin() as db:
            await db.execute(
                delete(SupportChatModel).where(
                    SupportChatModel.id == chat_id, SupportChatModel.owner_id == owner_id
                )
            )

    async def _update(self, condition, **values) -> None:
        async with self._session_factory.begin() as db:
            await db.execute(update(SupportChatModel).where(condition).values(**values))


def _to_entity(row: SupportChatModel) -> SupportChat:
    return SupportChat(
        id=row.id,
        telegram_chat_id=row.telegram_chat_id,
        owner_id=row.owner_id,
        title=row.title,
        chat_type=ChatType(row.chat_type),
        active=row.active,
        admin_ids=frozenset(json.loads(row.admin_ids)) if row.admin_ids else frozenset(),
    )
