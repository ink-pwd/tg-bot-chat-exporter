import re
from datetime import time

_TIME = re.compile(r"(\d{1,2})[:.](\d{2})")


def parse_time(text: str) -> time | None:
    """«7:45», «07:45», «07.45» → время."""
    match = _TIME.fullmatch(text.strip())
    if match is None:
        return None
    try:
        return time(int(match[1]), int(match[2]))
    except ValueError:
        return None
