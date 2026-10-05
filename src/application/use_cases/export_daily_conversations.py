import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from application.dto.export import CachedExport, ExportSummary
from application.errors import CachedFileUnavailable, SessionRevoked
from application.interfaces.export_cache import ExportCache
from application.interfaces.export_delivery import ExportDelivery
from application.interfaces.telegram_message_gateway import TelegramMessageGateway
from application.services.keyed_locks import KeyedLocks
from domain.entities.daily_conversation_export import DailyConversationExport
from domain.entities.telegram_account import TelegramAccount
from domain.enums.account_status import AccountStatus
from domain.errors import AccountNotFound, AccountRevoked, InvalidExportDay
from domain.repositories.telegram_account_repository import TelegramAccountRepository
from domain.repositories.telegram_session_repository import TelegramSessionRepository
from domain.value_objects.day_range import DayRange

logger = logging.getLogger(__name__)

# прошедший день почти не меняется; сегодняшний ещё идёт
FINISHED_DAY_TTL = timedelta(hours=24)
CURRENT_DAY_TTL = timedelta(minutes=10)


def utc_now() -> datetime:
    return datetime.now(UTC)


class ExportDailyConversations:
    """Выгрузка переписок аккаунта за день: владелец → кеш → Telegram → файл."""

    def __init__(
        self,
        accounts: TelegramAccountRepository,
        sessions: TelegramSessionRepository,
        gateway: TelegramMessageGateway,
        cache: ExportCache,
        delivery: ExportDelivery,
        locks: KeyedLocks,
        timezone: ZoneInfo,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._accounts = accounts
        self._sessions = sessions
        self._gateway = gateway
        self._cache = cache
        self._delivery = delivery
        self._locks = locks
        self._timezone = timezone
        self._clock = clock

    def today(self) -> date:
        return DayRange.today(self._clock(), self._timezone).day

    async def check_access(self, user_id: int, account_id: int) -> TelegramAccount:
        """Аккаунт принадлежит пользователю и его сессия действует."""
        account = await self._accounts.get_owned(account_id, user_id)
        if account is None:
            raise AccountNotFound()
        if account.status is AccountStatus.REVOKED:
            raise AccountRevoked()
        return account

    async def execute(
        self, user_id: int, account_id: int, day: date, *, refresh: bool = False
    ) -> ExportSummary:
        # владелец проверяется до кеша: кеш не должен стать обходным путём к чужим данным
        account = await self.check_access(user_id, account_id)

        requested_at = self._clock()
        day_range = DayRange(day, self._timezone)
        if day_range.is_future(requested_at):
            raise InvalidExportDay()

        if not refresh and (summary := await self._from_cache(user_id, account, day_range)):
            return summary

        async with self._locks.hold((account.id, day_range.day, self._timezone.key)):
            # пока ждали блокировку, ту же выгрузку мог закончить параллельный запрос
            cached = await self._cache.get(account.id, day_range)
            if cached is not None and (not refresh or cached.exported_at >= requested_at):
                if summary := await self._deliver_cached(user_id, account, day_range, cached):
                    return summary
            return await self._export(user_id, account, day_range)

    async def _from_cache(
        self, user_id: int, account: TelegramAccount, day: DayRange
    ) -> ExportSummary | None:
        cached = await self._cache.get(account.id, day)
        if cached is None:
            return None
        return await self._deliver_cached(user_id, account, day, cached)

    async def _deliver_cached(
        self, user_id: int, account: TelegramAccount, day: DayRange, cached: CachedExport
    ) -> ExportSummary | None:
        if cached.file_id is not None:
            try:
                await self._delivery.resend(user_id, account, day, cached)
            except CachedFileUnavailable:
                await self._cache.delete(account.id, day)
                return None
        logger.info("Daily export served from cache: account=%s day=%s", account.id, day.day)
        return ExportSummary(
            account=account,
            day=day,
            conversations_count=cached.conversations_count,
            messages_count=cached.messages_count,
            exported_at=cached.exported_at,
            from_cache=True,
        )

    async def _export(self, user_id: int, account: TelegramAccount, day: DayRange) -> ExportSummary:
        session = await self._sessions.get(account.id)
        if session is None:
            await self._revoke(account)
            raise AccountRevoked()

        logger.info("Daily export started: account=%s day=%s", account.id, day.day)
        try:
            fetched = await self._gateway.fetch_day(session, day)
        except SessionRevoked:
            await self._revoke(account)
            raise AccountRevoked() from None

        export = DailyConversationExport(
            account_id=account.id,
            profile=fetched.profile,
            phone=fetched.phone,
            day=day,
            exported_at=self._clock(),
            conversations=fetched.conversations,
        )
        file_id = await self._delivery.send(user_id, export) if export.messages_count else None

        ttl = FINISHED_DAY_TTL if day.is_finished(export.exported_at) else CURRENT_DAY_TTL
        await self._cache.put(
            account.id,
            day,
            CachedExport(file_id, export.conversations_count, export.messages_count, export.exported_at),
            ttl,
        )
        logger.info(
            "Daily export completed: account=%s day=%s conversations=%s messages=%s",
            account.id,
            day.day,
            export.conversations_count,
            export.messages_count,
        )
        return ExportSummary(
            account=account,
            day=day,
            conversations_count=export.conversations_count,
            messages_count=export.messages_count,
            exported_at=export.exported_at,
            from_cache=False,
        )

    async def _revoke(self, account: TelegramAccount) -> None:
        logger.warning("Account session revoked: account=%s", account.id)
        await self._accounts.mark_revoked(account.id, account.owner_id)
        await self._sessions.delete(account.id)
