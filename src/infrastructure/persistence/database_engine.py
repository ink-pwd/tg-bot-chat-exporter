"""Подключение к MySQL: движок SQLAlchemy и фабрика сессий."""
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def create_engine(database_url: str) -> AsyncEngine:
    # MySQL закрывает простаивающие соединения (wait_timeout), поэтому
    # проверяем соединение перед выдачей и периодически пересоздаём
    return create_async_engine(database_url, pool_pre_ping=True, pool_recycle=3600)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)
