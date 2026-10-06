import asyncio
import logging
from datetime import timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats
from redis.asyncio import Redis

from application.services.keyed_locks import KeyedLocks
from application.services.user_timezones import UserTimezones
from application.use_cases.analyze_daily_questions import AnalyzeDailyQuestions
from application.use_cases.configure_auto_export import ConfigureAutoExport
from application.use_cases.export_daily_conversations import ExportDailyConversations, utc_now
from application.use_cases.manage_support_chats import ManageSupportChats
from application.use_cases.record_chat_messages import RecordChatMessages
from application.use_cases.run_auto_exports import RunAutoExports
from infrastructure.cache.redis_export_cache import RedisExportCache
from infrastructure.config.logging import setup_logging
from infrastructure.config.settings import load_settings
from infrastructure.nlp.heuristic_message_classifier import HeuristicMessageClassifier
from infrastructure.nlp.intent_classifier import ModelIntentClassifier
from infrastructure.nlp.lemmatizer import Lemmatizer
from infrastructure.nlp.text_normalizer import TextNormalizer, load_concept_labels
from infrastructure.nlp.tfidf_question_clusterer import TfidfQuestionClusterer
from infrastructure.persistence.database import create_engine, create_session_factory
from infrastructure.persistence.repositories.bot_user_repository import SqlBotUserRepository
from infrastructure.persistence.repositories.chat_message_repository import (
    SqlChatMessageRepository,
)
from infrastructure.persistence.repositories.export_schedule_repository import (
    SqlExportScheduleRepository,
)
from infrastructure.persistence.repositories.support_chat_repository import (
    SqlSupportChatRepository,
)
from infrastructure.scheduler import run_periodically
from infrastructure.security.message_cipher import MessageCipher
from infrastructure.telegram.bot.aiogram_chat_gateway import AiogramChatGateway
from presentation.telegram.auto_export_notifier import AiogramAutoExportNotifier
from presentation.telegram.export_delivery import AiogramExportDelivery
from presentation.telegram.handlers import auto_export, chats, common, export, groups
from presentation.telegram.handlers import settings as settings_handlers
from presentation.telegram.middlewares.access import AccessMiddleware

logger = logging.getLogger(__name__)

# как часто планировщик проверяет, кому пора выгружаться
SCHEDULER_INTERVAL_SECONDS = 60
# как часто удаляются сообщения старше срока хранения
RETENTION_INTERVAL_SECONDS = 60 * 60

# состояние диалога (ожидание даты, времени) — не дольше 15 минут
FSM_TTL_SECONDS = 15 * 60


async def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level, settings.log_dir, settings.log_retention_days)

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    users = SqlBotUserRepository(session_factory)
    chat_repo = SqlSupportChatRepository(session_factory)
    message_repo = SqlChatMessageRepository(
        session_factory, MessageCipher(settings.message_encryption_keys)
    )
    schedule_repo = SqlExportScheduleRepository(session_factory)
    timezones = UserTimezones(users, settings.default_timezone)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    chat_gateway = AiogramChatGateway(bot)
    storage = RedisStorage.from_url(
        settings.redis_url, state_ttl=FSM_TTL_SECONDS, data_ttl=FSM_TTL_SECONDS
    )
    cache_redis = Redis.from_url(settings.redis_url, decode_responses=True)

    normalizer = TextNormalizer.from_resources(Lemmatizer())
    analyzer = AnalyzeDailyQuestions(
        HeuristicMessageClassifier(),
        normalizer,
        ModelIntentClassifier(normalizer),
        TfidfQuestionClusterer(normalizer, load_concept_labels()),
    )
    export_use_case = ExportDailyConversations(
        chat_repo,
        message_repo,
        chat_gateway,
        RedisExportCache(cache_redis),
        AiogramExportDelivery(bot),
        analyzer,
        KeyedLocks(),
        timezones,
        max_concurrent_exports=settings.export_concurrency,
    )
    auto_exports = RunAutoExports(
        schedule_repo, timezones, export_use_case, AiogramAutoExportNotifier(bot), utc_now
    )

    async def purge_old_messages() -> None:
        deleted = await message_repo.delete_sent_before(
            utc_now() - timedelta(days=settings.message_retention_days)
        )
        if deleted:
            logger.info("Old messages deleted: %s", deleted)

    access = AccessMiddleware(settings.allowed_user_ids)
    dp = Dispatcher(
        storage=storage,
        access=access,
        chats=ManageSupportChats(users, chat_repo, chat_gateway),
        recorder=RecordChatMessages(chat_repo, message_repo),
        export=export_use_case,
        auto_export=ConfigureAutoExport(schedule_repo, timezones, utc_now),
        timezones=timezones,
    )
    dp.update.outer_middleware(access)

    # меню и выгрузки — только в личном чате с ботом
    private = Router(name="private")
    private.message.filter(F.chat.type == ChatType.PRIVATE)
    private.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)
    private.include_routers(
        common.router,
        chats.router,
        export.router,
        auto_export.router,
        settings_handlers.router,
    )
    dp.include_routers(groups.router, private)

    background = [
        asyncio.create_task(run_periodically(auto_exports.run_due, SCHEDULER_INTERVAL_SECONDS)),
        asyncio.create_task(run_periodically(purge_old_messages, RETENTION_INTERVAL_SECONDS)),
    ]
    logger.info("Bot started")
    try:
        # кнопка «Меню» у поля ввода в личке; в беседах клиенты команд бота не видят
        await bot.set_my_commands(
            [BotCommand(command="start", description="Главное меню")],
            scope=BotCommandScopeAllPrivateChats(),
        )
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception:
        logger.critical("Bot crashed", exc_info=True)
        raise
    finally:
        for task in background:
            task.cancel()
        await storage.close()
        await cache_redis.aclose()
        await engine.dispose()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
