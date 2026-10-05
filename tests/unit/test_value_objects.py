import pytest

from domain.errors import InvalidPhoneNumber
from domain.value_objects.phone_number import PhoneNumber
from domain.value_objects.telegram_session import TelegramSession


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+380501234567", "+380501234567"),
        ("380501234567", "+380501234567"),
        (" +380 (50) 123-45-67 ", "+380501234567"),
        ("+1 202 555 0143", "+12025550143"),
    ],
)
def test_phone_number_is_normalized(raw, expected):
    assert PhoneNumber.parse(raw).value == expected


@pytest.mark.parametrize("raw", ["", "+", "12345", "+38050abc4567", "+1234567890123456"])
def test_invalid_phone_number(raw):
    with pytest.raises(InvalidPhoneNumber):
        PhoneNumber.parse(raw)


def test_session_value_is_hidden_from_repr():
    session = TelegramSession("1BVtsOK8Bu-secret")

    assert "secret" not in repr(session)
    assert "secret" not in str(session)


def test_empty_session_is_rejected():
    with pytest.raises(ValueError):
        TelegramSession("")
