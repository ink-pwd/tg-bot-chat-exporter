from enum import IntEnum
from typing import Protocol


class ExportStage(IntEnum):
    """Этапы выгрузки по порядку — по ним пользователь видит, сколько осталось."""

    COLLECTING = 1  # сообщения бесед за день из базы и админы бесед из Telegram
    ANALYZING = 2  # обращения, типы запросов, время ответа
    SENDING = 3  # JSON и HTML-отчёт формируются и отправляются


class ExportProgress(Protocol):
    async def stage(self, stage: ExportStage) -> None:
        """Сообщает о начале этапа. Ошибки показа прогресса не должны ломать выгрузку."""
        ...
