"""Выгрузка переписок за день через Telethon.

Объекты Telethon дальше этого модуля не уходят — всё переводится в сущности domain.
"""
import asyncio
import logging

from telethon import TelegramClient, errors, utils
from telethon.tl.custom.dialog import Dialog
from telethon.tl.custom.message import Message
from telethon.tl.types import Channel, Chat, User

from application.dto.export import FetchedDay
from application.errors import SessionRevoked
from domain.entities.conversation import Conversation
from domain.entities.support_message import SupportMessage
from domain.enums.chat_type import ChatType
from domain.value_objects.day_range import DayRange
from domain.value_objects.telegram_profile import TelegramProfile
from domain.value_objects.telegram_session import TelegramSession
from infrastructure.telegram.client.client_factory import TelethonClientFactory
from infrastructure.telegram.client.errors import disconnect_quietly, translate_error

logger = logging.getLogger(__name__)

# чаты, из которых аккаунт выгнали или которые стали недоступны, пропускаем
_SKIPPABLE_DIALOG_ERRORS = (
    errors.ChannelPrivateError,
    errors.ChannelInvalidError,
    errors.ChatAdminRequiredError,
)

_MEDIA_ATTRIBUTES = (
    "photo", "video", "voice", "video_note", "audio", "sticker",
    "gif", "document", "contact", "geo", "poll",
)


class TelethonMessageGateway:
    def __init__(
        self,
        clients: TelethonClientFactory,
        *,
        max_concurrent_exports: int = 3,
        flood_sleep_threshold: int = 120,
    ) -> None:
        self._clients = clients
        # одновременно открытых выгрузок не больше N — не перегружаем ни сервер, ни Telegram
        self._semaphore = asyncio.Semaphore(max_concurrent_exports)
        self._flood_sleep_threshold = flood_sleep_threshold

    async def fetch_day(self, session: TelegramSession, day: DayRange) -> FetchedDay:
        async with self._semaphore:
            client = self._clients.create(
                session.value, flood_sleep_threshold=self._flood_sleep_threshold
            )
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    raise SessionRevoked()
                me = await client.get_me()
                conversations = await _conversations(client, day)
            except Exception as exc:
                raise translate_error(exc) from exc
            finally:
                await disconnect_quietly(client)
        return FetchedDay(profile=to_profile(me), phone=me.phone, conversations=conversations)


async def _conversations(client: TelegramClient, day: DayRange) -> list[Conversation]:
    conversations = []
    async for dialog in client.iter_dialogs():
        # последний раз в диалоге писали до начала дня — сообщений за день в нём нет
        if dialog.date is None or dialog.date < day.start:
            continue
        try:
            messages = await _messages(client, dialog, day)
        except _SKIPPABLE_DIALOG_ERRORS as exc:
            logger.warning("Dialog skipped during export: %s", type(exc).__name__)
            continue
        if messages:
            conversations.append(
                Conversation(
                    chat_id=dialog.id,
                    title=dialog.name or "",
                    chat_type=chat_type(dialog.entity),
                    messages=messages,
                )
            )
    return conversations


async def _messages(client: TelegramClient, dialog: Dialog, day: DayRange) -> list[SupportMessage]:
    messages = []
    # offset_date: сообщения строго раньше конца дня, от новых к старым
    async for message in client.iter_messages(dialog.entity, offset_date=day.end):
        if message.date < day.start:
            break
        messages.append(to_support_message(message, dialog.id))
    messages.reverse()
    return messages


def to_profile(user: User) -> TelegramProfile:
    return TelegramProfile(
        telegram_user_id=user.id,
        display_name=utils.get_display_name(user) or str(user.id),
        username=user.username,
    )


def chat_type(entity: object) -> ChatType:
    if isinstance(entity, User):
        return ChatType.BOT if entity.bot else ChatType.PRIVATE
    if isinstance(entity, Chat):
        return ChatType.GROUP
    if isinstance(entity, Channel):
        return ChatType.SUPERGROUP if entity.megagroup else ChatType.CHANNEL
    return ChatType.UNKNOWN


def media_type(message: Message) -> str | None:
    if not message.media:
        return None
    for attribute in _MEDIA_ATTRIBUTES:
        if getattr(message, attribute, None):
            return attribute
    return type(message.media).__name__


def forwarded_from(message: Message) -> str | None:
    forward = message.fwd_from
    if not forward:
        return None
    if forward.from_name:
        return forward.from_name
    if forward.from_id:
        return str(utils.get_peer_id(forward.from_id))
    return None


def to_support_message(message: Message, chat_id: int) -> SupportMessage:
    return SupportMessage(
        id=message.id,
        chat_id=chat_id,
        sender_id=message.sender_id,
        sender_name=utils.get_display_name(message.sender) if message.sender else None,
        text=message.message or "",
        sent_at=message.date,
        edited_at=message.edit_date,
        is_outgoing=bool(message.out),
        reply_to_id=message.reply_to_msg_id,
        forwarded_from=forwarded_from(message),
        media_type=media_type(message),
        action=type(message.action).__name__ if message.action else None,
    )
