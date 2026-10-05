import re
from dataclasses import dataclass

from domain.errors import InvalidPhoneNumber

_SEPARATORS = re.compile(r"[\s\-()]")
_VALID = re.compile(r"\+\d{7,15}")


@dataclass(frozen=True)
class PhoneNumber:
    value: str

    @classmethod
    def parse(cls, raw: str) -> "PhoneNumber":
        phone = _SEPARATORS.sub("", raw.strip())
        if not phone.startswith("+"):
            phone = "+" + phone
        if not _VALID.fullmatch(phone):
            raise InvalidPhoneNumber()
        return cls(phone)
