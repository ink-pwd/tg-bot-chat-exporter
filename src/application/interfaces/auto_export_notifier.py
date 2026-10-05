from datetime import date
from typing import Protocol

from application.dto.export import ExportSummary
from application.errors import ApplicationError
from domain.entities.telegram_account import TelegramAccount
from domain.errors import DomainError


class AutoExportNotifier(Protocol):
    """Сообщения владельцу о ночной автовыгрузке. Ошибки отправки не пробрасываются."""

    async def completed(self, user_id: int, summary: ExportSummary) -> None: ...

    async def account_revoked(self, user_id: int, account: TelegramAccount) -> None: ...

    async def failed(
        self, user_id: int, account: TelegramAccount, day: date, error: ApplicationError | DomainError
    ) -> None: ...
