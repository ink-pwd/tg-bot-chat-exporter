"""Беседа в выгрузке: название, тип чата и её сообщения за день."""
from dataclasses import dataclass, field

from domain.entities.support_message import SupportMessage
from domain.enums.chat_type import ChatType


@dataclass(frozen=True)
class Conversation:
    chat_id: int
    title: str
    chat_type: ChatType
    messages: list[SupportMessage] = field(default_factory=list)  # от старых к новым
