from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramProfile:
    """Кто авторизован в Telegram-аккаунте."""

    telegram_user_id: int
    display_name: str
    username: str | None
