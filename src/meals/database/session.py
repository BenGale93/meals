"""Database interaction module."""

import typing as t
from collections.abc import AsyncGenerator  # noqa: TC003

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///meals.db"


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models.

    All other models should inherit from this class.
    """


async_engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, t.Any]:  # pragma: no cover # This is overridden in tests
    """Get a database session.

    To be used for dependency injection.
    """
    async with async_session() as session, session.begin():
        yield session


async def init_models() -> None:
    """Create tables if they don't already exist.

    In a real-life example we would use Alembic to manage migrations.
    """
    async with async_engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all)  # noqa: ERA001
        await conn.run_sync(Base.metadata.create_all)
