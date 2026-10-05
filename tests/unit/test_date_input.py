from datetime import date

import pytest

from presentation.telegram.date_input import parse_day

TODAY = date(2026, 10, 5)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("04.10", date(2026, 10, 4)),
        ("4.10", date(2026, 10, 4)),
        ("04/10", date(2026, 10, 4)),
        ("04.10.2026", date(2026, 10, 4)),
        ("04.10.26", date(2026, 10, 4)),
        ("2026-10-04", date(2026, 10, 4)),
        (" 05.10 ", date(2026, 10, 5)),
        # без года — ближайший прошедший: 30.12 в октябре это прошлый декабрь
        ("30.12", date(2025, 12, 30)),
    ],
)
def test_parse_day(text, expected):
    assert parse_day(text, TODAY) == expected


@pytest.mark.parametrize("text", ["", "вчера", "32.10", "04.13", "2026-02-30", "4 октября"])
def test_invalid_day(text):
    assert parse_day(text, TODAY) is None
