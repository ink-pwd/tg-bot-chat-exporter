import pytest

from infrastructure.config.settings import ConfigError, load_settings

BASE_ENV = {
    "BOT_TOKEN": "123:abc",
    "TELEGRAM_API_ID": "42",
    "TELEGRAM_API_HASH": "hash",
    "DATABASE_URL": "mysql+aiomysql://u:p@db/x",
    "REDIS_URL": "redis://redis:6379/0",
    "SESSION_ENCRYPTION_KEY": "new-key, old-key",
}


def test_loads_settings():
    settings = load_settings({**BASE_ENV, "ALLOWED_USER_IDS": "1, 2,,3"})

    assert settings.telegram_api_id == 42
    assert settings.session_encryption_keys == ("new-key", "old-key")
    assert settings.allowed_user_ids == frozenset({1, 2, 3})


def test_allowed_users_empty_by_default():
    assert load_settings(BASE_ENV).allowed_user_ids == frozenset()


def test_secrets_are_not_in_repr():
    text = repr(load_settings(BASE_ENV))

    assert "123:abc" not in text
    assert "new-key" not in text
    assert "u:p@" not in text


@pytest.mark.parametrize("missing", ["BOT_TOKEN", "TELEGRAM_API_ID", "SESSION_ENCRYPTION_KEY"])
def test_missing_variable(missing):
    env = {k: v for k, v in BASE_ENV.items() if k != missing}

    with pytest.raises(ConfigError, match=missing):
        load_settings(env)


def test_non_numeric_api_id():
    with pytest.raises(ConfigError):
        load_settings({**BASE_ENV, "TELEGRAM_API_ID": "abc"})


def test_log_settings():
    settings = load_settings({**BASE_ENV, "LOG_DIR": "/app/logs", "LOG_RETENTION_DAYS": "14"})

    assert settings.log_dir == "/app/logs"
    assert settings.log_retention_days == 14


def test_log_dir_empty_by_default():
    settings = load_settings(BASE_ENV)

    assert settings.log_dir is None
    assert settings.log_retention_days == 30


def test_log_retention_must_be_positive():
    with pytest.raises(ConfigError):
        load_settings({**BASE_ENV, "LOG_RETENTION_DAYS": "0"})
