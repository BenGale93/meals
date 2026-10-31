import typing as t
from datetime import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from meals.app import create_app
from meals.database.session import Base, create_async_db_engine, get_db
from meals.schemas import CreateRecipeRequest, CreateUserRequest, RecipeStep, TimingsCreate, TimingSteps

if t.TYPE_CHECKING:
    from fastapi import FastAPI


@pytest.fixture
def user_one():
    return CreateUserRequest(user_name="User One")


@pytest.fixture
def user_two():
    return CreateUserRequest(user_name="User Two")


@pytest_asyncio.fixture
async def db_engine(tmp_path):
    """Create the per-test database and engine."""
    engine = create_async_db_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_connection(db_engine):
    """Hold one outer transaction that is rolled back after the test.

    Everything the app and the tests do happens inside this transaction (via
    savepoints), so a test can never leak data or schema changes into another
    one, even if a request really commits.
    """
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        # SQLite's legacy transaction mode defers the real BEGIN until the first
        # DML statement. A savepoint opened before that would commit on its own
        # instead of joining the outer transaction, so force the BEGIN now.
        await connection.exec_driver_sql("BEGIN")
        yield connection
        await transaction.rollback()


@pytest_asyncio.fixture
async def db_session(db_connection):
    """A test-side session that joins the outer transaction."""
    session = AsyncSession(bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
    yield session
    await session.close()


@pytest.fixture
def test_get_db(db_connection):
    """Mirror production ``get_db``: a fresh session per request, inside a savepoint."""

    async def override_get_db() -> t.AsyncIterator[AsyncSession]:
        async with (
            AsyncSession(
                bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            ) as session,
            session.begin(),
        ):
            yield session

    return override_get_db


@pytest.fixture
def test_app(test_get_db) -> FastAPI:
    """Create a fresh app per test, with the database dependency overridden.

    A new app keeps ``dependency_overrides`` out of the module-global
    application, so overrides cannot leak between tests (or between workers).
    Test requests get their own session, exactly like production, rather than
    sharing one bare session with the test body.
    """
    app = create_app()
    app.dependency_overrides[get_db] = test_get_db
    return app


@pytest_asyncio.fixture()
async def client(test_app, user_one):
    """Create an http client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=user_one.auth_headers()) as client:
        response = await client.post("/api/v1/users", json=user_one.model_dump())
        response.raise_for_status()
        yield client


@pytest_asyncio.fixture()
async def bad_client(test_app, user_one):
    """Create an unauthenticated http client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/users", json=user_one.model_dump())
        response.raise_for_status()
        yield client


@pytest_asyncio.fixture()
async def user_two_client(test_app, user_two):
    """Create an unauthenticated http client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=user_two.auth_headers()) as client:
        response = await client.post("/api/v1/users", json=user_two.model_dump())
        response.raise_for_status()
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
def sausage_recipe():
    return CreateRecipeRequest.model_validate(
        {
            "name": "Sausage Pasta",
            "instructions": "Test instructions for sausage pasta",
            "ingredients": [{"name": "Sausage", "quantity": 6.0, "unit": "units"}],
            "labels": [
                {"category": "meat", "sub_category": "pork"},
                {"category": "time", "sub_category": "slow"},
            ],
        }
    )


@pytest.fixture
def burger_recipe():
    return CreateRecipeRequest.model_validate(
        {
            "name": "Burger",
            "instructions": "Test instructions for burgers",
            "ingredients": [{"name": "Beef", "quantity": 500.0, "unit": "g"}],
            "labels": [
                {"category": "meat", "sub_category": "beef"},
                {"category": "time", "sub_category": "quick"},
            ],
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
