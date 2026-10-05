import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from application.errors import ApplicationError, ExportTooLarge, RecipientUnavailable, TooManyAttempts
from application.interfaces.auto_export_notifier import AutoExportNotifier
from application.services.user_timezones import UserTimezones
from application.use_cases.export_daily_conversations import ExportDailyConversations
from domain.entities.export_schedule import ExportSchedule
from domain.errors import AccountNotFound, AccountRevoked
from domain.repositories.export_schedule_repository import ExportScheduleRepository
from domain.repositories.telegram_account_repository import TelegramAccountRepository

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_DELAY = timedelta(minutes=5)


@dataclass
class _Attempts:
    count: int
    retry_at: datetime


class RunAutoExports:
    """Один проход планировщика: выгружает всё, чему пора.

    Повторы после сбоев считаются в памяти: после перезапуска бота
    счётчик начинается заново — это безопасно, просто попыток будет больше.
    """

    def __init__(
        self,
        schedules: ExportScheduleRepository,
        accounts: TelegramAccountRepository,
        timezones: UserTimezones,
        export: ExportDailyConversations,
        notifier: AutoExportNotifier,
        clock: Callable[[], datetime],
    ) -> None:
        self._schedules = schedules
        self._accounts = accounts
        self._timezones = timezones
        self._export = export
        self._notifier = notifier
        self._clock = clock
        self._attempts: dict[tuple[int, date], _Attempts] = {}

    async def run_due(self) -> None:
        now = self._clock()
        jobs = []
        for schedule in await self._schedules.list_enabled():
            timezone = await self._timezones.get(schedule.owner_id)
            day = schedule.due_day(now, timezone)
            if day is None:
                continue
            attempts = self._attempts.get((schedule.account_id, day))
            if attempts is not None and attempts.retry_at > now:
                continue
            jobs.append(self._run(schedule, day))
        # параллельность ограничена шлюзом выгрузки (EXPORT_CONCURRENCY)
        await asyncio.gather(*jobs)

    async def _run(self, schedule: ExportSchedule, day: date) -> None:
        account_id, owner_id = schedule.account_id, schedule.owner_id
        logger.info("Auto export started: account=%s day=%s", account_id, day)
        try:
            summary = await self._export.execute(owner_id, account_id, day)
        except AccountNotFound:
            return  # аккаунт отключили — расписание удалено вместе с ним
        except AccountRevoked:
            await self._schedules.disable(account_id)
            if account := await self._accounts.get_owned(account_id, owner_id):
                await self._notifier.account_revoked(owner_id, account)
            return
        except RecipientUnavailable:
            logger.warning("Auto exports disabled, bot is blocked: user=%s", owner_id)
            await self._schedules.disable_all_owned(owner_id)
            return
        except ExportTooLarge as exc:
            await self._give_up(schedule, day, exc)
            return
        except Exception as exc:
            await self._retry_later(schedule, day, exc)
            return

        self._attempts.pop((account_id, day), None)
        await self._schedules.mark_done(account_id, day)
        await self._notifier.completed(owner_id, summary)
        logger.info("Auto export completed: account=%s day=%s", account_id, day)

    async def _retry_later(self, schedule: ExportSchedule, day: date, exc: Exception) -> None:
        key = (schedule.account_id, day)
        count = self._attempts[key].count + 1 if key in self._attempts else 1
        if not isinstance(exc, ApplicationError):
            logger.error("Auto export crashed: account=%s", schedule.account_id, exc_info=exc)
        if count >= MAX_ATTEMPTS:
            await self._give_up(schedule, day, exc)
            return
        delay = RETRY_DELAY
        if isinstance(exc, TooManyAttempts) and exc.retry_after_seconds:
            delay = max(delay, timedelta(seconds=exc.retry_after_seconds))
        self._attempts[key] = _Attempts(count, self._clock() + delay)
        logger.warning(
            "Auto export failed, will retry: account=%s day=%s attempt=%s error=%s",
            schedule.account_id,
            day,
            count,
            type(exc).__name__,
        )

    async def _give_up(self, schedule: ExportSchedule, day: date, exc: Exception) -> None:
        self._attempts.pop((schedule.account_id, day), None)
        # день помечается выполненным, чтобы не повторять бесконечно; вручную выгрузить можно
        await self._schedules.mark_done(schedule.account_id, day)
        logger.error(
            "Auto export gave up: account=%s day=%s error=%s",
            schedule.account_id,
            day,
            type(exc).__name__,
        )
        if account := await self._accounts.get_owned(schedule.account_id, schedule.owner_id):
            error = exc if isinstance(exc, ApplicationError) else ApplicationError()
            await self._notifier.failed(schedule.owner_id, account, day, error)
