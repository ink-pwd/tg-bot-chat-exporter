from enum import StrEnum


class AccountStatus(StrEnum):
    ACTIVE = "active"
    # сессия завершена со стороны Telegram (например, из «Устройств»), нужен повторный вход
    REVOKED = "revoked"
