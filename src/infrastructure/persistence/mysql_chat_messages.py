"""Хранилище сообщений бесед в MySQL: зашифрованный текст, выборка за день, удаление старых."""
import json
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.support_message import SupportMessage
from domain.value_objects.day_range import DayRange
from infrastructure.persistence.sqlalchemy_models import ChatMessageModel
from infrastructure.security.message_cipher import MessageCipher


class MySqlChatMessageRepository:
    """Даты хранятся в UTC без часового пояса (DATETIME в MySQL)."""

    def __init__(self, session_factory: async_sessionmaker, cipher: MessageCipher) -> None:
        self._session_factory = session_factory
        self._cipher = cipher

    async def add(self, chat_id: int, message: SupportMessage) -> None:
        stmt = (
            insert(ChatMessageModel)
            .values(
                telegram_chat_id=message.chat_id,
                message_id=message.id,
                support_chat_id=chat_id,
                sender_id=message.sender_id,
                sent_at=_to_db(message.sent_at),
                edited_at=_to_db(message.edited_at),
                reply_to_id=message.reply_to_id,
                media_type=message.media_type,
                action=message.action,
                encrypted_content=self._encrypt(message),
            )
            # Telegram может доставить одно обновление повторно
            .prefix_with("IGNORE")
        )
        async with self._session_factory.begin() as db:
            await db.execute(stmt)

    async def update_edited(self, message: SupportMessage) -> None:
        async with self._session_factory.begin() as db:
            await db.execute(
                update(ChatMessageModel)
                .where(
                    ChatMessageModel.telegram_chat_id == message.chat_id,
                    ChatMessageModel.message_id == message.id,
                )
                .values(
                    edited_at=_to_db(message.edited_at),
                    media_type=message.media_type,
                    encrypted_content=self._encrypt(message),
                )
            )

    async def list_for_day(self, chat_ids: list[int], day: DayRange) -> dict[int, list[SupportMessage]]:
        if not chat_ids:
            return {}
        async with self._session_factory() as db:
            rows = await db.scalars(
                select(ChatMessageModel)
                .where(
                    ChatMessageModel.support_chat_id.in_(chat_ids),
                    ChatMessageModel.sent_at >= _to_db(day.start),
                    ChatMessageModel.sent_at < _to_db(day.end),
                )
                .order_by(ChatMessageModel.sent_at, ChatMessageModel.message_id)
            )
            result: dict[int, list[SupportMessage]] = defaultdict(list)
            for row in rows:
                result[row.support_chat_id].append(self._to_entity(row))
        return dict(result)

    async def delete_sent_before(self, moment: datetime) -> int:
        async with self._session_factory.begin() as db:
            result = await db.execute(
                delete(ChatMessageModel).where(ChatMessageModel.sent_at < _to_db(moment))
            )
            return result.rowcount

    def _encrypt(self, message: SupportMessage) -> bytes:
        content = {
            "text": message.text,
            "sender_name": message.sender_name,
            "forwarded_from": message.forwarded_from,
        }
        return self._cipher.encrypt(json.dumps(content, ensure_ascii=False))

    def _to_entity(self, row: ChatMessageModel) -> SupportMessage:
        content = json.loads(self._cipher.decrypt(row.encrypted_content))
        return SupportMessage(
            id=row.message_id,
            chat_id=row.telegram_chat_id,
            sender_id=row.sender_id,
            sender_name=content["sender_name"],
            text=content["text"],
            sent_at=row.sent_at.replace(tzinfo=UTC),
            edited_at=row.edited_at.replace(tzinfo=UTC) if row.edited_at else None,
            from_support=False,  # определяется при выгрузке
            reply_to_id=row.reply_to_id,
            forwarded_from=content["forwarded_from"],
            media_type=row.media_type,
            action=row.action,
        )


def _to_db(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return moment.astimezone(UTC).replace(tzinfo=None)
