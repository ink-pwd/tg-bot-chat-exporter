from enum import StrEnum


class ChatType(StrEnum):
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"
    UNKNOWN = "unknown"
