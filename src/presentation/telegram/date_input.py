import re
from datetime import date, time

_DOTTED = re.compile(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2}|\d{4}))?")
_ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_TIME = re.compile(r"(\d{1,2})[:.](\d{2})")


def parse_day(text: str, today: date) -> date | None:
    """«04.10», «4.10.2026», «04/10/26», «2026-10-04» → дата.

    Без года берётся ближайший прошедший такой день: в январе «30.12» —
    это декабрь прошлого года.
    """
    text = text.strip()
    try:
        if match := _ISO.fullmatch(text):
            year, month, day = map(int, match.groups())
            return date(year, month, day)
        if match := _DOTTED.fullmatch(text):
            day, month = int(match[1]), int(match[2])
            if match[3] is None:
                candidate = date(today.year, month, day)
                return candidate if candidate <= today else date(today.year - 1, month, day)
            year = int(match[3])
            return date(year + 2000 if year < 100 else year, month, day)
    except ValueError:
        return None
    return None


def parse_time(text: str) -> time | None:
    """«7:45», «07:45», «07.45» → время."""
    match = _TIME.fullmatch(text.strip())
    if match is None:
        return None
    try:
        return time(int(match[1]), int(match[2]))
    except ValueError:
        return None
