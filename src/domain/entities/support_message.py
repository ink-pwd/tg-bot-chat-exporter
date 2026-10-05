from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SupportMessage:
    id: int
    chat_id: int
    sender_id: int | None
    sender_name: str | None
    text: str
    sent_at: datetime  # aware, UTC
    edited_at: datetime | None
    is_outgoing: bool
    reply_to_id: int | None
    forwarded_from: str | None
    media_type: str | None
    action: str | None
