"""Сценарий: выгрузка бесед пользователя за день — кеш, база, анализ, отправка JSON и отчёта."""
import asyncio
import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from application.dto.daily_report import DailyQuestionReport
from application.dto.export_summary import CachedExport, ExportSummary
from application.ports.export_cache import ExportCache
from application.ports.export_delivery import ExportDelivery, ExportProgress, ExportStage
from application.ports.storage_repositories import ChatMessageRepository, SupportChatRepository
from application.ports.telegram_chat_actions import TelegramChatGateway
from application.services.keyed_locks import KeyedLocks
from application.services.user_timezones import UserTimezones
from application.use_cases.analyze_daily_questions import AnalyzeDailyQuestions
from application.user_facing_errors import ApplicationError, CachedFileUnavailable
from domain.business_rule_errors import ExportDayTooOld, InvalidExportDay
from domain.entities.conversation import Conversation
from domain.entities.daily_conversation_export import DailyConversationExport
from domain.entities.support_chat import SupportChat
from domain.value_objects.day_range import DayRange

logger = logging.getLogger(__name__)

# выгрузить можно сегодня и 6 предыдущих дней — столько хранятся сообщения
EXPORT_WINDOW_DAYS = 7
# прошедший день почти не меняется; сегодняшний ещё идёт
FINISHED_DAY_TTL = timedelta(hours=24)
CURRENT_DAY_TTL = timedelta(minutes=10)


def utc_now() -> datetime:
    return datetime.now(UTC)


class ExportDailyConversations:
    """Выгрузка всех бесед пользователя за день: кеш → сохранённые сообщения → JSON + отчёт.

    Пользователь выгружает только свои беседы: список берётся по владельцу,
    а кеш хранится отдельно для каждого пользователя.
    """

    def __init__(
        self,
        chats: SupportChatRepository,
        messages: ChatMessageRepository,
        gateway: TelegramChatGateway,
        cache: ExportCache,
        delivery: ExportDelivery,
        analyzer: AnalyzeDailyQuestions,
        locks: KeyedLocks,
        timezones: UserTimezones,
        *,
        max_concurrent_exports: int = 3,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._chats = chats
        self._messages = messages
        self._gateway = gateway
        self._cache = cache
        self._delivery = delivery
        self._analyzer = analyzer
        self._locks = locks
        self._timezones = timezones
        # одновременно собирается не больше N выгрузок: анализ нагружает процессор
        self._semaphore = asyncio.Semaphore(max_concurrent_exports)
        self._clock = clock

    async def today(self, user_id: int) -> date:
        """Сегодняшний день в часовом поясе пользователя."""
        return DayRange.today(self._clock(), await self._timezones.get(user_id)).day

    async def available_days(self, user_id: int) -> list[date]:
        """Дни, которые можно выгрузить: от сегодня назад, по часовому поясу пользователя."""
        today = await self.today(user_id)
        return [today - timedelta(days=offset) for offset in range(EXPORT_WINDOW_DAYS)]

    async def execute(
        self,
        user_id: int,
        day: date,
        *,
        refresh: bool = False,
        progress: ExportProgress | None = None,
    ) -> ExportSummary:
        requested_at = self._clock()
        timezone = await self._timezones.get(user_id)
        day_range = DayRange(day, timezone)
        if day_range.is_future(requested_at):
            raise InvalidExportDay()
        oldest = DayRange.today(requested_at, timezone).day - timedelta(days=EXPORT_WINDOW_DAYS - 1)
        if day < oldest:
            raise ExportDayTooOld()

        progress = progress or _NoProgress()
        if not refresh and (summary := await self._from_cache(user_id, day_range, progress)):
            return summary

        async with self._locks.hold((user_id, day_range.day, day_range.timezone.key)):
            # пока ждали блокировку, ту же выгрузку мог закончить параллельный запрос
            cached = await self._cache.get(user_id, day_range)
            if cached is not None and (not refresh or cached.exported_at >= requested_at):
                if summary := await self._deliver_cached(user_id, day_range, cached, progress):
                    return summary
            async with self._semaphore:
                return await self._export(user_id, day_range, progress)

    async def _from_cache(
        self, user_id: int, day: DayRange, progress: ExportProgress
    ) -> ExportSummary | None:
        cached = await self._cache.get(user_id, day)
        if cached is None:
            return None
        return await self._deliver_cached(user_id, day, cached, progress)

    async def _deliver_cached(
        self, user_id: int, day: DayRange, cached: CachedExport, progress: ExportProgress
    ) -> ExportSummary | None:
        if not cached.file_ids:
            return None  # пустых выгрузок в кеше быть не должно — собираем заново
        await progress.stage(ExportStage.SENDING)
        try:
            await self._delivery.resend(user_id, day, cached)
        except CachedFileUnavailable:
            await self._cache.delete(user_id, day)
            return None
        logger.info("Daily export served from cache: user=%s day=%s", user_id, day.day)
        return ExportSummary(
            day=day,
            conversations_count=cached.conversations_count,
            messages_count=cached.messages_count,
            exported_at=cached.exported_at,
            from_cache=True,
        )

    async def _export(self, user_id: int, day: DayRange, progress: ExportProgress) -> ExportSummary:
        logger.info("Daily export started: user=%s day=%s", user_id, day.day)
        await progress.stage(ExportStage.COLLECTING)
        export = DailyConversationExport(
            owner_id=user_id,
            day=day,
            exported_at=self._clock(),
            conversations=await self._conversations(user_id, day),
        )
        if not export.messages_count:
            # пустые файлы не отправляем и не кешируем: сообщения ещё могут прийти
            logger.info("Daily export: nothing recorded: user=%s day=%s", user_id, day.day)
            return ExportSummary(
                day=day,
                conversations_count=0,
                messages_count=0,
                exported_at=export.exported_at,
                from_cache=False,
            )
        await progress.stage(ExportStage.ANALYZING)
        report = await self._analyze(export)
        await progress.stage(ExportStage.SENDING)
        file_ids = tuple(await self._delivery.send(user_id, export, report))

        ttl = FINISHED_DAY_TTL if day.is_finished(export.exported_at) else CURRENT_DAY_TTL
        await self._cache.put(
            user_id,
            day,
            CachedExport(file_ids, export.conversations_count, export.messages_count, export.exported_at),
            ttl,
        )
        logger.info(
            "Daily export completed: user=%s day=%s conversations=%s messages=%s",
            user_id,
            day.day,
            export.conversations_count,
            export.messages_count,
        )
        return ExportSummary(
            day=day,
            conversations_count=export.conversations_count,
            messages_count=export.messages_count,
            exported_at=export.exported_at,
            from_cache=False,
        )

    async def _conversations(self, user_id: int, day: DayRange) -> list[Conversation]:
        chats = await self._chats.list_owned(user_id)
        by_chat = await self._messages.list_for_day([chat.id for chat in chats], day)
        conversations = []
        for chat in chats:
            messages = by_chat.get(chat.id)
            if not messages:
                continue
            support = await self._support_ids(chat)
            conversations.append(
                Conversation(
                    chat_id=chat.telegram_chat_id,
                    title=chat.title,
                    chat_type=chat.chat_type,
                    messages=[replace(m, from_support=m.sender_id in support) for m in messages],
                )
            )
        return conversations

    async def _support_ids(self, chat: SupportChat) -> frozenset[int]:
        """Актуальные админы из Telegram, а если бота в беседе уже нет — последние известные."""
        if not chat.active:
            return chat.support_ids()
        try:
            admin_ids = await self._gateway.get_admin_ids(chat.telegram_chat_id)
        except ApplicationError:
            logger.warning("Chat admins not refreshed, using saved list: chat=%s", chat.id)
            return chat.support_ids()
        if admin_ids != chat.admin_ids:
            await self._chats.save_admin_ids(chat.id, admin_ids)
        return replace(chat, admin_ids=admin_ids).support_ids()

    async def _analyze(self, export: DailyConversationExport) -> DailyQuestionReport | None:
        """Отчёт строится в отдельном потоке: это вычисления, они не должны блокировать бота.

        Сбой анализа не должен лишать пользователя выгрузки — тогда уйдёт только JSON.
        """
        try:
            return await asyncio.to_thread(self._analyzer.analyze, export)
        except Exception:
            logger.exception("Question analysis failed: user=%s", export.owner_id)
            return None


class _NoProgress:
    """Автовыгрузка и прочие вызовы без пользователя перед экраном."""

    async def stage(self, stage: ExportStage) -> None:
        pass
