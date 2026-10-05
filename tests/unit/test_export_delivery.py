from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.methods import SendDocument

from application.dto.export import CachedExport
from application.errors import CachedFileUnavailable, RecipientUnavailable
from domain.entities.telegram_account import TelegramAccount
from domain.enums.account_status import AccountStatus
from presentation.telegram.export_delivery import AiogramExportDelivery
from tests.unit.test_export_file import make_export
from tests.unit.test_report_html import make_report


class FakeBot:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.documents = []
        self.groups = []

    async def send_document(self, chat_id, document, caption=None):
        if self.error:
            raise self.error
        self.documents.append((chat_id, document, caption))
        return SimpleNamespace(document=SimpleNamespace(file_id=f"doc-{len(self.documents)}"))

    async def send_media_group(self, chat_id, media):
        if self.error:
            raise self.error
        self.groups.append((chat_id, media))
        return [SimpleNamespace(document=SimpleNamespace(file_id=f"group-{i}")) for i in range(len(media))]


ACCOUNT = TelegramAccount(1, 100, 555, "Поддержка", "support", AccountStatus.ACTIVE)


async def test_json_and_report_are_sent_as_album():
    bot = FakeBot()

    file_ids = await AiogramExportDelivery(bot).send(100, make_export(), make_report())

    assert file_ids == ["group-0", "group-1"]
    chat_id, media = bot.groups[0]
    assert chat_id == 100
    assert [m.media.filename for m in media] == ["support_2026-10-05.json", "support_2026-10-05_report.html"]
    assert media[0].caption is None and "Поддержка" in media[1].caption


async def test_without_report_only_json_is_sent():
    bot = FakeBot()

    file_ids = await AiogramExportDelivery(bot).send(100, make_export(), None)

    assert file_ids == ["doc-1"]
    assert bot.groups == []


async def test_cached_album_is_resent_by_file_ids():
    bot = FakeBot()
    cached = CachedExport(("a", "b"), 1, 2, datetime(2026, 10, 5, tzinfo=UTC))

    await AiogramExportDelivery(bot).resend(100, ACCOUNT, make_export().day, cached)

    assert [m.media for m in bot.groups[0][1]] == ["a", "b"]


async def test_stale_file_id():
    bot = FakeBot(TelegramBadRequest(method=SendDocument(chat_id=1, document="x"), message="wrong file id"))
    cached = CachedExport(("a",), 1, 2, datetime(2026, 10, 5, tzinfo=UTC))

    with pytest.raises(CachedFileUnavailable):
        await AiogramExportDelivery(bot).resend(100, ACCOUNT, make_export().day, cached)


async def test_blocked_bot():
    bot = FakeBot(TelegramForbiddenError(method=SendDocument(chat_id=1, document="x"), message="blocked"))

    with pytest.raises(RecipientUnavailable):
        await AiogramExportDelivery(bot).send(100, make_export(), make_report())
