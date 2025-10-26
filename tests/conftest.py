from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from meals.app import app
from meals.database.session import Base, get_db

if TYPE_CHECKING:
    from fastapi import FastAPI


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///test.db")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session = async_sessionmaker(engine)()
    yield session
    await session.close()


@pytest.fixture
def test_app(db_session: AsyncSession) -> FastAPI:
    """Create a test app with overridden dependencies."""
    app.dependency_overrides[get_db] = lambda: db_session
    return app


@pytest_asyncio.fixture()
async def client(test_app):
    """Create an http client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
