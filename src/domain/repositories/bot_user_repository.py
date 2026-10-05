from typing import Protocol


class BotUserRepository(Protocol):
    async def ensure_exists(self, user_id: int) -> None: ...
