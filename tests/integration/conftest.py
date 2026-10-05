import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from infrastructure.persistence.database import create_engine, create_session_factory

ROOT = Path(__file__).resolve().parents[2]
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.integration


def pytest_collection_modifyitems(items):
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL не задан")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def migrated_database():
    """Схема создаётся миграциями — заодно проверяем, что они применяются и откатываются."""
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.attributes["database_url"] = TEST_DATABASE_URL
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
    yield
    command.downgrade(config, "base")


@pytest.fixture
async def session_factory(migrated_database):
    engine = create_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in ("export_schedules", "telegram_sessions", "telegram_accounts", "bot_users"):
            await conn.execute(text(f"TRUNCATE TABLE {table}"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    yield create_session_factory(engine)
    await engine.dispose()
