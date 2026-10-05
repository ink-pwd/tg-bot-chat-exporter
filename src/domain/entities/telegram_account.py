from dataclasses import dataclass

from domain.enums.account_status import AccountStatus


@dataclass
class TelegramAccount:
    id: int
    owner_id: int
    telegram_user_id: int
    display_name: str
    username: str | None
    status: AccountStatus

    def belongs_to(self, user_id: int) -> bool:
        return self.owner_id == user_id
