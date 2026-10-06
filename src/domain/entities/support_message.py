"""Сообщение из беседы — только те поля, что нужны выгрузке и анализу."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SupportMessage:
    id: int  # id сообщения в Telegram, уникален в пределах chat_id
    chat_id: int  # Telegram id беседы, в которой сообщение отправлено
    sender_id: int | None
    sender_name: str | None
    text: str
    sent_at: datetime  # aware, UTC
    edited_at: datetime | None
    from_support: bool  # определяется при выгрузке по списку поддержки беседы
    reply_to_id: int | None
    forwarded_from: str | None
    media_type: str | None
    action: str | None
