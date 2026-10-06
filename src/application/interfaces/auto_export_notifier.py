from datetime import date
from typing import Protocol

from application.dto.export import ExportSummary
from application.errors import ApplicationError
from domain.errors import DomainError


class AutoExportNotifier(Protocol):
    """Сообщения владельцу о ночной автовыгрузке. Ошибки отправки не пробрасываются."""

    async def completed(self, user_id: int, summary: ExportSummary) -> None: ...

    async def failed(self, user_id: int, day: date, error: ApplicationError | DomainError) -> None: ...
