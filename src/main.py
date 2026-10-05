import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from application.use_cases.login_telegram_account import LoginTelegramAccount
from application.use_cases.manage_telegram_accounts import ManageTelegramAccounts
from infrastructure.config.logging import setup_logging
from infrastructure.config.settings import load_settings
from infrastructure.persistence.database import create_engine, create_session_factory
from infrastructure.persistence.repositories.bot_user_repository import SqlBotUserRepository
from infrastructure.persistence.repositories.telegram_account_repository import (
    SqlTelegramAccountRepository,
)
from infrastructure.persistence.repositories.telegram_session_repository import (
    SqlTelegramSessionRepository,
)
from infrastructure.security.session_cipher import SessionCipher
from infrastructure.telegram.client.telethon_auth_gateway import TelethonAuthGateway
from presentation.telegram.handlers import accounts, common, login
from presentation.telegram.middlewares.access import AccessMiddleware

logger = logging.getLogger(__name__)

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
    auth_gateway = TelethonAuthGateway(settings.telegram_api_id, settings.telegram_api_hash)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = RedisStorage.from_url(
        settings.redis_url, state_ttl=FSM_TTL_SECONDS, data_ttl=FSM_TTL_SECONDS
    )
    dp = Dispatcher(
        storage=storage,
        login=LoginTelegramAccount(auth_gateway, users, account_repo, session_repo),
        accounts=ManageTelegramAccounts(auth_gateway, account_repo, session_repo),
    )
    dp.update.outer_middleware(AccessMiddleware(settings.allowed_user_ids))
    dp.include_routers(common.router, accounts.router, login.router)

    cleanup = asyncio.create_task(auth_gateway.run_cleanup())
    logger.info("Bot started")
    try:
        await dp.start_polling(bot)
    except Exception:
        logger.critical("Bot crashed", exc_info=True)
        raise
    finally:
        cleanup.cancel()
        await auth_gateway.close()
        await storage.close()
        await engine.dispose()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
