import typing as t
from datetime import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from meals.app import app
from meals.database.session import Base, get_db
from meals.schemas import CreateRecipeRequest, RecipeStep, TimingsCreate, TimingSteps


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
def test_app(db_session: AsyncSession) -> t.Any:
    """Create a test app with overridden dependencies."""
    app.dependency_overrides[get_db] = lambda: db_session
    return app


@pytest_asyncio.fixture()
async def client(test_app):
    """Create an http client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def carrots_recipe():
    return CreateRecipeRequest.model_validate(
        {
            "name": "Carrot Surprise",
            "instructions": "Test instructions",
            "ingredients": [{"name": "Carrot", "quantity": 10.0, "unit": "units"}],
        }
    )


@pytest.fixture
def sweets_recipe():
    return CreateRecipeRequest.model_validate(
        {
            "name": "Sweets",
            "instructions": "More test instructions",
            "ingredients": [{"name": "sweets", "quantity": 50.0, "unit": "units"}],
        }
    )


@pytest.fixture
def take_away():
    return CreateRecipeRequest.model_validate(
        {
            "name": "Take Away",
            "instructions": "",
            "ingredients": [],
        }
    )


@pytest.fixture
def dummy_timings():
    return TimingsCreate(
        steps=TimingSteps([RecipeStep(description="Start", offset=-60), RecipeStep(description="Finish", offset=0)]),
        finish_time=time(18, 0, 0),
    )
