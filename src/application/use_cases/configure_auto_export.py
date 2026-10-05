import logging
from collections.abc import Callable
from datetime import datetime, time

from application.services.user_timezones import UserTimezones
from domain.entities.export_schedule import ExportSchedule
from domain.entities.telegram_account import TelegramAccount
from domain.enums.account_status import AccountStatus
from domain.errors import AccountNotFound, AccountRevoked
from domain.repositories.export_schedule_repository import ExportScheduleRepository
from domain.repositories.telegram_account_repository import TelegramAccountRepository

logger = logging.getLogger(__name__)


class ConfigureAutoExport:
    """Включение, смена времени и выключение автовыгрузки своих аккаунтов."""

    def __init__(
        self,
        accounts: TelegramAccountRepository,
        schedules: ExportScheduleRepository,
        timezones: UserTimezones,
        clock: Callable[[], datetime],
    ) -> None:
        self._accounts = accounts
        self._schedules = schedules
        self._timezones = timezones
        self._clock = clock

    async def get(self, user_id: int, account_id: int) -> ExportSchedule:
        account = await self._owned(user_id, account_id)
        schedule = await self._schedules.get_owned(account.id, user_id)
        return schedule or ExportSchedule.new(account.id, user_id)

    async def set_time(self, user_id: int, account_id: int, local_time: time) -> ExportSchedule:
        account = await self._owned(user_id, account_id)
        if account.status is AccountStatus.REVOKED:
            raise AccountRevoked()
        current = await self._schedules.get_owned(account.id, user_id) or ExportSchedule.new(
            account.id, user_id
        )
        timezone = await self._timezones.get(user_id)
        schedule = current.scheduled_at(local_time, self._clock(), timezone)
        await self._schedules.save(schedule)
        logger.info(
            "Auto export scheduled: account=%s time=%s tz=%s",
            account.id,
            local_time.strftime("%H:%M"),
            timezone.key,
        )
        return schedule

    async def disable(self, user_id: int, account_id: int) -> ExportSchedule:
        schedule = await self.get(user_id, account_id)
        if schedule.enabled:
            schedule = schedule.disabled()
            await self._schedules.save(schedule)
            logger.info("Auto export disabled: account=%s", account_id)
        return schedule

    async def list_enabled(self, user_id: int) -> list[tuple[TelegramAccount, ExportSchedule]]:
        accounts = {account.id: account for account in await self._accounts.list_owned(user_id)}
        return [
            (accounts[schedule.account_id], schedule)
            for schedule in await self._schedules.list_owned(user_id)
            if schedule.enabled and schedule.account_id in accounts
        ]

    async def _owned(self, user_id: int, account_id: int) -> TelegramAccount:
        account = await self._accounts.get_owned(account_id, user_id)
        if account is None:
            raise AccountNotFound()
        return account
