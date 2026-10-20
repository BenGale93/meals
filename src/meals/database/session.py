"""Database interaction module."""

import typing as t
from collections.abc import AsyncGenerator  # noqa: TC003

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from meals.settings import database_url

if t.TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.pool import ConnectionPoolEntry

DATABASE_URL = database_url()


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models.

    All other models should inherit from this class.
    """


def _enable_sqlite_foreign_keys(dbapi_connection: DBAPIConnection, _: ConnectionPoolEntry) -> None:
    """Turn on SQLite foreign-key enforcement for every new connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_async_db_engine(url: str) -> AsyncEngine:
    """Create an async engine with SQLite foreign keys enforced."""
    engine = create_async_engine(url, echo=False)
    event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    return engine


async_engine = create_async_db_engine(DATABASE_URL)
async_session = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, t.Any]:  # pragma: no cover # This is overridden in tests
    """Get a database session.

    To be used for dependency injection.
    """
    async with async_session() as session, session.begin():
        yield session
