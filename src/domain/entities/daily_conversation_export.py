from dataclasses import dataclass
from datetime import datetime

from domain.entities.conversation import Conversation
from domain.value_objects.day_range import DayRange
from domain.value_objects.telegram_profile import TelegramProfile


@dataclass(frozen=True)
class DailyConversationExport:
    account_id: int
    profile: TelegramProfile
    phone: str | None
    day: DayRange
    exported_at: datetime
    conversations: list[Conversation]

    @property
    def conversations_count(self) -> int:
        return len(self.conversations)

    @property
    def messages_count(self) -> int:
        return sum(len(c.messages) for c in self.conversations)
