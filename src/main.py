import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from application.services.keyed_locks import KeyedLocks
from application.services.user_timezones import UserTimezones
from application.use_cases.configure_auto_export import ConfigureAutoExport
from application.use_cases.export_daily_conversations import ExportDailyConversations, utc_now
from application.use_cases.login_telegram_account import LoginTelegramAccount
from application.use_cases.manage_telegram_accounts import ManageTelegramAccounts
from application.use_cases.run_auto_exports import RunAutoExports
from infrastructure.cache.redis_export_cache import RedisExportCache
from infrastructure.config.logging import setup_logging
from infrastructure.config.settings import load_settings
from infrastructure.persistence.database import create_engine, create_session_factory
from infrastructure.persistence.repositories.bot_user_repository import SqlBotUserRepository
from infrastructure.persistence.repositories.export_schedule_repository import (
    SqlExportScheduleRepository,
)
from infrastructure.persistence.repositories.telegram_account_repository import (
    SqlTelegramAccountRepository,
)
from infrastructure.persistence.repositories.telegram_session_repository import (
    SqlTelegramSessionRepository,
)
from infrastructure.scheduler import run_periodically
from infrastructure.security.session_cipher import SessionCipher
from infrastructure.telegram.client.client_factory import TelethonClientFactory
from infrastructure.telegram.client.telethon_auth_gateway import TelethonAuthGateway
from infrastructure.telegram.client.telethon_message_gateway import TelethonMessageGateway
from presentation.telegram.auto_export_notifier import AiogramAutoExportNotifier
from presentation.telegram.export_delivery import AiogramExportDelivery
from presentation.telegram.handlers import accounts, auto_export, common, export, login
from presentation.telegram.handlers import settings as settings_handlers
from presentation.telegram.middlewares.access import AccessMiddleware

logger = logging.getLogger(__name__)

# как часто планировщик проверяет, каким аккаунтам пора выгружаться
SCHEDULER_INTERVAL_SECONDS = 60

# состояние диалога (шаг входа, введённые цифры кода) — не дольше 15 минут
FSM_TTL_SECONDS = 15 * 60


async def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level, settings.log_dir, settings.log_retention_days)

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    cipher = SessionCipher(settings.session_encryption_keys)

    users = SqlBotUserRepository(session_factory)
    account_repo = SqlTelegramAccountRepository(session_factory)
    session_repo = SqlTelegramSessionRepository(session_factory, cipher)
    schedule_repo = SqlExportScheduleRepository(session_factory)
    timezones = UserTimezones(users, settings.default_timezone)
    clients = TelethonClientFactory(settings.telegram_api_id, settings.telegram_api_hash)
    auth_gateway = TelethonAuthGateway(clients)
    message_gateway = TelethonMessageGateway(
        clients, max_concurrent_exports=settings.export_concurrency
    )

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = RedisStorage.from_url(
        settings.redis_url, state_ttl=FSM_TTL_SECONDS, data_ttl=FSM_TTL_SECONDS
    )
    cache_redis = Redis.from_url(settings.redis_url, decode_responses=True)

    export_use_case = ExportDailyConversations(
        account_repo,
        session_repo,
        message_gateway,
        RedisExportCache(cache_redis),
        AiogramExportDelivery(bot),
        KeyedLocks(),
        timezones,
    )
    auto_exports = RunAutoExports(
        schedule_repo,
        account_repo,
        timezones,
        export_use_case,
        AiogramAutoExportNotifier(bot),
        utc_now,
    )

    dp = Dispatcher(
        storage=storage,
        login=LoginTelegramAccount(auth_gateway, users, account_repo, session_repo),
        accounts=ManageTelegramAccounts(auth_gateway, account_repo, session_repo),
        export=export_use_case,
        auto_export=ConfigureAutoExport(account_repo, schedule_repo, timezones, utc_now),
        timezones=timezones,
    )
    dp.update.outer_middleware(AccessMiddleware(settings.allowed_user_ids))
    dp.include_routers(
        common.router,
        accounts.router,
        export.router,
        auto_export.router,
        settings_handlers.router,
        login.router,
    )

    background = [
        asyncio.create_task(auth_gateway.run_cleanup()),
        asyncio.create_task(run_periodically(auto_exports.run_due, SCHEDULER_INTERVAL_SECONDS)),
    ]
    logger.info("Bot started")
    try:
        await dp.start_polling(bot)
    except Exception:
        logger.critical("Bot crashed", exc_info=True)
        raise
    finally:
        for task in background:
            task.cancel()
        await auth_gateway.close()
        await storage.close()
        await cache_redis.aclose()
        await engine.dispose()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
