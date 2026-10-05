import pytest

from application import errors as app_errors
from domain import errors as domain_errors
from presentation.telegram.texts import error_text

USER_FACING_ERRORS = [
    domain_errors.AccountNotFound(),
    domain_errors.AccountOwnedByAnotherUser(),
    domain_errors.InvalidPhoneNumber(),
    app_errors.LoginNotStarted(),
    app_errors.InvalidCode(),
    app_errors.CodeExpired(),
    app_errors.CodeResendUnavailable(),
    app_errors.InvalidPassword(),
    app_errors.PhoneNumberRejected(),
    app_errors.TooManyAttempts(),
    app_errors.TooManyAttempts(90),
    app_errors.TelegramUnavailable(),
]


@pytest.mark.parametrize("exc", USER_FACING_ERRORS, ids=lambda e: type(e).__name__)
def test_every_user_facing_error_has_text(exc):
    assert error_text(exc)


def test_flood_wait_shows_duration():
    assert "2 мин" in error_text(app_errors.TooManyAttempts(90))


def test_unexpected_error_has_no_text():
    assert error_text(RuntimeError("boom")) is None


@pytest.mark.parametrize(
    "exc",
    [domain_errors.AccountRevoked(), domain_errors.InvalidExportDay(), app_errors.ExportTooLarge()],
    ids=lambda e: type(e).__name__,
)
def test_export_errors_have_text(exc):
    assert error_text(exc)
