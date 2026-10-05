from typing import Protocol

from application.dto.export import FetchedDay
from domain.value_objects.day_range import DayRange
from domain.value_objects.telegram_session import TelegramSession


class TelegramMessageGateway(Protocol):
    async def fetch_day(self, session: TelegramSession, day: DayRange) -> FetchedDay:
        """Все переписки аккаунта с сообщениями за день.

        Raises:
            SessionRevoked: сессия больше не действует.
            TooManyAttempts: Telegram попросил подождать дольше разумного.
            TelegramUnavailable: прочие сбои.
        """
        ...
