"""Сообщения aiogram → SupportMessage. Объекты aiogram дальше presentation не уходят."""
from datetime import UTC, datetime

from aiogram.enums import ContentType, MessageEntityType
from aiogram.types import (
    Message,
    MessageOriginChannel,
    MessageOriginChat,
    MessageOriginHiddenUser,
    MessageOriginUser,
)

from domain.entities.support_message import SupportMessage
from domain.enums.chat_type import ChatType

# порядок важен: у анимации заполнено и поле document
_MEDIA = (
    ("animation", "gif"),
    ("photo", "photo"),
    ("video", "video"),
    ("voice", "voice"),
    ("video_note", "video_note"),
    ("audio", "audio"),
    ("sticker", "sticker"),
    ("document", "document"),
    ("contact", "contact"),
    ("venue", "geo"),
    ("location", "geo"),
    ("poll", "poll"),
    ("dice", "dice"),
    ("story", "story"),
)
# обычные сообщения; всё остальное — служебные события (вступил, сменил название, …)
_REGULAR_CONTENT = {ContentType.TEXT} | {ContentType(attribute) for attribute, _ in _MEDIA}

_CHAT_TYPES = {
    "private": ChatType.PRIVATE,
    "group": ChatType.GROUP,
    "supergroup": ChatType.SUPERGROUP,
    "channel": ChatType.CHANNEL,
}


def chat_type(value: str) -> ChatType:
    return _CHAT_TYPES.get(value, ChatType.UNKNOWN)


def to_support_message(message: Message) -> SupportMessage:
    sender_id, sender_name = _sender(message)
    return SupportMessage(
        id=message.message_id,
        chat_id=message.chat.id,
        sender_id=sender_id,
        sender_name=sender_name,
        text=message.text or message.caption or "",
        sent_at=message.date,
        # edit_date в Bot API — unix-время числом, в отличие от date
        edited_at=datetime.fromtimestamp(message.edit_date, UTC) if message.edit_date else None,
        from_support=False,
        reply_to_id=message.reply_to_message.message_id if message.reply_to_message else None,
        forwarded_from=_forwarded_from(message),
        media_type=_media_type(message),
        action=_action(message),
    )


def starts_with_command(message: Message) -> bool:
    """/start и другие команды боту — не часть переписки с клиентом."""
    return any(
        entity.type == MessageEntityType.BOT_COMMAND and entity.offset == 0
        for entity in message.entities or ()
    )


def _sender(message: Message) -> tuple[int | None, str | None]:
    # анонимный админ пишет от имени беседы, канал — от имени канала
    if message.sender_chat is not None:
        return message.sender_chat.id, message.sender_chat.title
    if message.from_user is not None:
        return message.from_user.id, message.from_user.full_name
    return None, None


def _action(message: Message) -> str | None:
    content_type = message.content_type
    if content_type in _REGULAR_CONTENT:
        return None
    return getattr(content_type, "value", str(content_type))


def _media_type(message: Message) -> str | None:
    for attribute, name in _MEDIA:
        if getattr(message, attribute, None):
            return name
    return None


def _forwarded_from(message: Message) -> str | None:
    match message.forward_origin:
        case MessageOriginUser(sender_user=user):
            return user.full_name
        case MessageOriginHiddenUser(sender_user_name=name):
            return name
        case MessageOriginChat(sender_chat=chat) | MessageOriginChannel(chat=chat):
            return chat.title or str(chat.id)
    return None
