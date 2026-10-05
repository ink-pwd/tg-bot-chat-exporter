from dataclasses import dataclass, field


@dataclass(frozen=True)
class TelegramSession:
    """Данные авторизованной сессии Telegram — по сути пароль от аккаунта.

    Значение скрыто из repr, чтобы случайно не попасть в логи и трейсбеки.
    """

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("empty session")
