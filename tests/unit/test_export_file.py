import gzip
import json
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from application.errors import ExportTooLarge
from domain.entities.daily_conversation_export import DailyConversationExport
from domain.value_objects.day_range import DayRange
from domain.value_objects.telegram_profile import TelegramProfile
from presentation.telegram.export_delivery import AiogramExportDelivery
from presentation.telegram.formatters.export_json import render_export_json
from tests.unit.export_fakes import conversation, message

KYIV = ZoneInfo("Europe/Kyiv")


def make_export(*messages, username: str | None = "support") -> DailyConversationExport:
    return DailyConversationExport(
        account_id=1,
        profile=TelegramProfile(555, "Поддержка", username),
        phone="380501234567",
        day=DayRange(date(2026, 10, 5), KYIV),
        exported_at=datetime(2026, 10, 5, 12, 0, tzinfo=UTC),
        conversations=[conversation(*messages)] if messages else [],
    )


def test_json_keeps_legacy_format_in_local_time():
    export = make_export(message(1, datetime(2026, 10, 5, 6, 30, tzinfo=UTC)))

    document = json.loads(render_export_json(export))

    assert document["date"] == "2026-10-05"
    assert document["timezone"] == "Europe/Kyiv"
    assert document["account"] == {
        "id": 555, "name": "Поддержка", "username": "support", "phone": "380501234567",
    }
    assert document["exported_at"] == "2026-10-05T15:00:00+03:00"
    chat = document["chats"][0]
    assert (chat["id"], chat["name"], chat["type"]) == (10, "Клиент", "private")
    assert chat["messages"][0] == {
        "id": 1,
        "date": "2026-10-05T09:30:00+03:00",
        "edit_date": None,
        "from_id": 1,
        "from": "Клиент",
        "out": False,
        "text": "Как изменить способ оплаты?",
        "reply_to": None,
        "forwarded_from": None,
        "media": None,
        "action": None,
    }


def test_json_is_utf8_not_escaped():
    content = render_export_json(make_export(message(1, datetime(2026, 10, 5, 6, 0, tzinfo=UTC))))

    assert "Как изменить способ оплаты?".encode() in content


def test_small_file_is_plain_json():
    delivery = AiogramExportDelivery(bot=None)

    content, filename = delivery.prepare_file(make_export(message(1, datetime(2026, 10, 5, 6, 0, tzinfo=UTC))))

    assert filename == "support_2026-10-05.json"
    json.loads(content)


def test_large_file_is_gzipped():
    delivery = AiogramExportDelivery(bot=None, compress_from_bytes=100)
    export = make_export(message(1, datetime(2026, 10, 5, 6, 0, tzinfo=UTC)))

    content, filename = delivery.prepare_file(export)

    assert filename == "support_2026-10-05.json.gz"
    assert json.loads(gzip.decompress(content))["date"] == "2026-10-05"


def test_too_large_file_is_rejected():
    delivery = AiogramExportDelivery(bot=None, compress_from_bytes=10**9, max_upload_bytes=100)

    with pytest.raises(ExportTooLarge):
        delivery.prepare_file(make_export(message(1, datetime(2026, 10, 5, 6, 0, tzinfo=UTC))))


def test_filename_without_username_uses_id():
    delivery = AiogramExportDelivery(bot=None)

    _, filename = delivery.prepare_file(make_export(username=None))

    assert filename == "555_2026-10-05.json"
