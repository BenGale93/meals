import datetime as dt
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from meals.database.models import RecipeIngredient, StoredPlannedDay, StoredRecipe, User
from meals.database.repository import PlanRepository, RecipeRepository, UserRepository
from meals.database.session import Base, create_async_db_engine, get_db
from meals.schemas import (
    CreateUserRequest,
    PlannedDay,
    PlannedDayResponse,
    PlannedRecipe,
    RecipeResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_get_db_commits_when_the_request_finishes(monkeypatch, tmp_path):
    engine = create_async_db_engine(f"sqlite+aiosqlite:///{tmp_path}/get_db.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine)
    monkeypatch.setattr("meals.database.session.async_session", session_factory)

    generator = get_db()
    session = await anext(generator)
    session.add(User(user_name="Committed"))

    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    async with session_factory() as check_session:
        user = (await check_session.scalars(select(User))).one()

    assert user.user_name == "Committed"

    await engine.dispose()


async def test_requests_use_independent_sessions(test_get_db):
    first = test_get_db()
    first_session = await anext(first)
    second = test_get_db()
    second_session = await anext(second)

    assert first_session is not second_session

    await second.aclose()
    await first.aclose()


async def test_request_commit_is_visible_to_the_test_session(client, db_session, carrots_recipe):
    response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
    response.raise_for_status()

    pk = response.json()["pk"]

    assert await db_session.get(StoredRecipe, pk) is not None


async def test_request_writes_stay_inside_the_test_transaction(client, db_engine, carrots_recipe):
    response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
    response.raise_for_status()

    # A separate connection cannot see the uncommitted outer transaction, so the
    # request's savepoint commit will be rolled back with the test.
    async with db_engine.connect() as other_connection:
        assert (await other_connection.scalars(select(StoredRecipe))).first() is None


async def test_foreign_keys_are_enforced(db_session: AsyncSession):
    assert (await db_session.execute(text("PRAGMA foreign_keys"))).scalar() == 1

    db_session.add(RecipeIngredient(recipe_pk=999, ingredient_pk=999, quantity=1, unit="unit"))

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_deleting_a_recipe_cascades_to_planned_days(client, db_session: AsyncSession, carrots_recipe):
    response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
    response.raise_for_status()
    recipe = PlannedRecipe.model_validate(response.json())

    response = await client.post("/api/v1/planned_day", json={"day": "2025-01-01", "recipe": recipe.model_dump()})
    response.raise_for_status()

    stored_recipe = await db_session.get(StoredRecipe, recipe.pk)
    assert stored_recipe is not None
    await db_session.delete(stored_recipe)
    await db_session.flush()

    planned_days = (await db_session.scalars(select(StoredPlannedDay))).all()
    assert planned_days == []


async def test_queries_eager_load_serialised_relationships(db_session: AsyncSession, carrots_recipe):
    """Every response relationship must survive the session, with no lazy load left.

    The ORM objects are detached (`expunge_all`) before Pydantic validates them, so a
    relationship that was not eager-loaded raises `DetachedInstanceError` here instead of
    becoming a `MissingGreenlet` 500 in production.
    """
    user = await UserRepository(db_session).create(CreateUserRequest(user_name="User One"))
    recipe_repo = RecipeRepository(db_session)
    plan_repo = PlanRepository(db_session)

    recipe = await recipe_repo.create(carrots_recipe, user.pk)
    day = dt.date(2025, 1, 1)
    await plan_repo.update(PlannedDay(day=day, recipe=PlannedRecipe(pk=recipe.pk, name=recipe.name)), user.pk)

    db_session.expunge_all()

    stored = await recipe_repo.get(recipe.pk, user.pk)
    assert stored is not None
    db_session.expunge_all()
    assert [ingredient.name for ingredient in RecipeResponse.model_validate(stored).ingredients] == ["Carrot"]

    stored_by_name = await recipe_repo.get_by_name(recipe.name, user.pk)
    assert stored_by_name is not None
    db_session.expunge_all()
    assert [ingredient.name for ingredient in RecipeResponse.model_validate(stored_by_name).ingredients] == ["Carrot"]

    stored_all = await recipe_repo.get_all(user.pk)
    db_session.expunge_all()
    responses = [RecipeResponse.model_validate(stored) for stored in stored_all]
    assert [response.name for response in responses] == [recipe.name]

    stored_like = await recipe_repo.is_like("Carrot", user.pk)
    db_session.expunge_all()
    responses = [RecipeResponse.model_validate(stored) for stored in stored_like]
    assert [response.name for response in responses] == [recipe.name]

    stored_plan = await plan_repo.update(
        PlannedDay(day=day, recipe=PlannedRecipe(pk=recipe.pk, name=recipe.name)), user.pk
    )
    db_session.expunge_all()
    assert PlannedDayResponse.model_validate(stored_plan).recipe == PlannedRecipe(pk=recipe.pk, name=recipe.name)

    stored_plans = await plan_repo.get_range(day, day, user.pk)
    db_session.expunge_all()
    responses = [PlannedDayResponse.model_validate(stored) for stored in stored_plans]
    assert [response.recipe for response in responses] == [PlannedRecipe(pk=recipe.pk, name=recipe.name)]
