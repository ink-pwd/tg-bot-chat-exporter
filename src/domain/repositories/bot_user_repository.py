from typing import Protocol


class BotUserRepository(Protocol):
    async def ensure_exists(self, user_id: int) -> None: ...

    async def get_timezone(self, user_id: int) -> str | None:
        """IANA-имя пояса (Europe/Kyiv) или None, если пользователь его не выбирал."""
        ...

    async def set_timezone(self, user_id: int, timezone: str) -> None: ...
