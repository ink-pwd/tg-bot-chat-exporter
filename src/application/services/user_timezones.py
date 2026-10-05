from functools import cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from domain.errors import InvalidTimezone
from domain.repositories.bot_user_repository import BotUserRepository


class UserTimezones:
    """Часовой пояс пользователя: выбранный в настройках или общий по умолчанию."""

    def __init__(self, users: BotUserRepository, default: ZoneInfo) -> None:
        self._users = users
        self._default = default

    async def get(self, user_id: int) -> ZoneInfo:
        name = await self._users.get_timezone(user_id)
        if name is None:
            return self._default
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            return self._default

    async def set(self, user_id: int, name: str) -> ZoneInfo:
        timezone = parse_timezone(name)
        await self._users.set_timezone(user_id, timezone.key)
        return timezone


def parse_timezone(name: str) -> ZoneInfo:
    """«europe/kyiv», «Europe/Kyiv», «utc» → ZoneInfo. Только имена из базы IANA."""
    canonical = _timezones_by_lower_name().get(name.strip().lower())
    if canonical is None:
        raise InvalidTimezone()
    return ZoneInfo(canonical)


@cache
def _timezones_by_lower_name() -> dict[str, str]:
    return {name.lower(): name for name in available_timezones()}
