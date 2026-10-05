import os
from dataclasses import dataclass, field


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    bot_token: str = field(repr=False)
    telegram_api_id: int
    telegram_api_hash: str = field(repr=False)
    database_url: str = field(repr=False)
    redis_url: str
    session_encryption_keys: tuple[str, ...] = field(repr=False)
    # пусто — бот доступен всем
    allowed_user_ids: frozenset[int] = frozenset()
    log_level: str = "INFO"
    # пусто — только консоль
    log_dir: str | None = None
    log_retention_days: int = 30


def load_settings(env: dict[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env

    def required(name: str) -> str:
        value = env.get(name, "").strip()
        if not value:
            raise ConfigError(f"Не задана переменная окружения {name}")
        return value

    def as_int(name: str, value: str) -> int:
        try:
            return int(value)
        except ValueError:
            raise ConfigError(f"{name} должна быть числом") from None

    retention_days = as_int("LOG_RETENTION_DAYS", env.get("LOG_RETENTION_DAYS", "30"))
    if retention_days < 1:
        raise ConfigError("LOG_RETENTION_DAYS должна быть не меньше 1")

    allowed = frozenset(
        as_int("ALLOWED_USER_IDS", part.strip())
        for part in env.get("ALLOWED_USER_IDS", "").split(",")
        if part.strip()
    )
    return Settings(
        bot_token=required("BOT_TOKEN"),
        telegram_api_id=as_int("TELEGRAM_API_ID", required("TELEGRAM_API_ID")),
        telegram_api_hash=required("TELEGRAM_API_HASH"),
        database_url=required("DATABASE_URL"),
        redis_url=required("REDIS_URL"),
        session_encryption_keys=tuple(
            key.strip() for key in required("SESSION_ENCRYPTION_KEY").split(",") if key.strip()
        ),
        allowed_user_ids=allowed,
        log_level=env.get("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        log_dir=env.get("LOG_DIR", "").strip() or None,
        log_retention_days=retention_days,
    )
