import contextlib
import logging

from telethon import TelegramClient, errors

from application.errors import (
    ApplicationError,
    PhoneNumberRejected,
    SessionRevoked,
    TelegramUnavailable,
    TooManyAttempts,
)

logger = logging.getLogger(__name__)

SESSION_REVOKED_ERRORS = (
    errors.AuthKeyUnregisteredError,
    errors.AuthKeyDuplicatedError,
    errors.SessionRevokedError,
    errors.SessionExpiredError,
    errors.UserDeactivatedError,
    errors.UserDeactivatedBanError,
)


def translate_error(exc: BaseException) -> ApplicationError:
    """Ошибки Telethon → ошибки приложения. Подробности остаются в логах."""
    if isinstance(exc, ApplicationError):
        return exc
    if isinstance(exc, SESSION_REVOKED_ERRORS):
        return SessionRevoked()
    if isinstance(exc, errors.FloodWaitError):
        return TooManyAttempts(exc.seconds)
    if isinstance(exc, (errors.PhoneNumberFloodError, errors.PhonePasswordFloodError)):
        return TooManyAttempts()
    if isinstance(
        exc,
        (
            errors.PhoneNumberInvalidError,
            errors.PhoneNumberBannedError,
            errors.PhoneNumberUnoccupiedError,
        ),
    ):
        return PhoneNumberRejected()
    logger.error("Telegram error: %s", type(exc).__name__, exc_info=exc)
    return TelegramUnavailable()


async def disconnect_quietly(client: TelegramClient) -> None:
    with contextlib.suppress(Exception):
        await client.disconnect()
