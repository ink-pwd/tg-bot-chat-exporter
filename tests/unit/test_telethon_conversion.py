from datetime import UTC, datetime
from types import SimpleNamespace

from telethon.tl.types import Channel, Chat, ChatPhotoEmpty, User

from domain.enums.chat_type import ChatType
from infrastructure.telegram.client.telethon_message_gateway import (
    chat_type,
    media_type,
    to_support_message,
)


def channel(megagroup: bool) -> Channel:
    return Channel(
        id=1, title="c", photo=ChatPhotoEmpty(), date=datetime.now(UTC), megagroup=megagroup
    )


def test_chat_types():
    assert chat_type(User(id=1, bot=False)) is ChatType.PRIVATE
    assert chat_type(User(id=1, bot=True)) is ChatType.BOT
    assert chat_type(Chat(id=1, title="g", photo=ChatPhotoEmpty(), participants_count=2, date=datetime.now(UTC), version=1)) is ChatType.GROUP
    assert chat_type(channel(megagroup=True)) is ChatType.SUPERGROUP
    assert chat_type(channel(megagroup=False)) is ChatType.CHANNEL
    assert chat_type(object()) is ChatType.UNKNOWN


def fake_message(**overrides) -> SimpleNamespace:
    fields = dict(
        id=7,
        sender_id=42,
        sender=User(id=42, first_name="Ирина", last_name="К"),
        message="Не приходит SMS",
        date=datetime(2026, 10, 5, 6, 0, tzinfo=UTC),
        edit_date=None,
        out=False,
        reply_to_msg_id=3,
        fwd_from=None,
        media=None,
        action=None,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_message_is_converted_to_domain():
    result = to_support_message(fake_message(), chat_id=10)

    assert result.id == 7
    assert result.chat_id == 10
    assert result.sender_name == "Ирина К"
    assert result.text == "Не приходит SMS"
    assert result.reply_to_id == 3
    assert result.media_type is None


def test_service_message_without_text():
    result = to_support_message(fake_message(message=None, sender=None), chat_id=10)

    assert result.text == ""
    assert result.sender_name is None


def test_forwarded_from_name():
    forward = SimpleNamespace(from_name="Канал новостей", from_id=None)

    assert to_support_message(fake_message(fwd_from=forward), chat_id=10).forwarded_from == "Канал новостей"


def test_media_type():
    assert media_type(fake_message(media=object(), photo=object())) == "photo"
    assert media_type(fake_message()) is None
