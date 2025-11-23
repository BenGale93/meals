import typing as t
from datetime import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from meals.app import app
from meals.database.session import Base, get_db
from meals.schemas import CreateRecipeRequest, CreateUserRequest, RecipeStep, TimingsCreate, TimingSteps


@pytest.fixture
def user_one():
    return CreateUserRequest(user_name="User One")


@pytest.fixture
def user_two():
    return CreateUserRequest(user_name="User Two")


@pytest_asyncio.fixture
async def db_session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")

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
async def client(test_app, user_one):
    """Create an http client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=user_one.auth_headers()) as client:
        _ = await client.post("/api/v1/users", json=user_one.model_dump())
        yield client


@pytest_asyncio.fixture()
async def bad_client(test_app, user_one):
    """Create an unauthenticated http client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        _ = await client.post("/api/v1/users", json=user_one.model_dump())
        yield client


@pytest_asyncio.fixture()
async def user_two_client(test_app, user_two):
    """Create an unauthenticated http client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=user_two.auth_headers()) as client:
        _ = await client.post("/api/v1/users", json=user_two.model_dump())
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
def pasta_recipe():
    return CreateRecipeRequest.model_validate(
        {
            "name": "Pasta",
            "instructions": "Test instructions for pasta",
            "ingredients": [{"name": "Pasta", "quantity": 1.0, "unit": "kg"}],
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
