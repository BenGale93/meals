import datetime as dt
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from meals.database.models import (
    Category,
    RecipeIngredient,
    StoredPlannedDay,
    StoredRecipe,
    StoredRecipeLabel,
    SubCategory,
    User,
)
from meals.database.repository import PlanRepository, RecipeRepository, UserRepository
from meals.database.session import Base, create_async_db_engine, get_db
from meals.schemas import (
    CreateUserRequest,
    Labels,
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
    recipe.labels.append(StoredRecipeLabel(sub_category=SubCategory(name="beef", category=Category(name="meat"))))
    await db_session.flush()
    day = dt.date(2025, 1, 1)
    await plan_repo.update(PlannedDay(day=day, recipe=PlannedRecipe(pk=recipe.pk, name=recipe.name)), user.pk)

    db_session.expunge_all()

    stored = await recipe_repo.get(recipe.pk, user.pk)
    assert stored is not None
    db_session.expunge_all()
    stored_response = RecipeResponse.model_validate(stored)
    assert [ingredient.name for ingredient in stored_response.ingredients] == ["Carrot"]
    assert [(label.category, label.sub_category) for label in stored_response.labels] == [("meat", "beef")]
    assert [str(label) for label in Labels.model_validate(stored.labels)] == ["meat::beef"]

    stored_by_name = await recipe_repo.get_by_name(recipe.name, user.pk)
    assert stored_by_name is not None
    db_session.expunge_all()
    stored_response = RecipeResponse.model_validate(stored_by_name)
    assert [ingredient.name for ingredient in stored_response.ingredients] == ["Carrot"]
    assert [(label.category, label.sub_category) for label in stored_response.labels] == [("meat", "beef")]

    stored_all = await recipe_repo.get_all(user.pk)
    db_session.expunge_all()
    responses = [RecipeResponse.model_validate(stored) for stored in stored_all]
    assert [response.name for response in responses] == [recipe.name]
    assert [(label.category, label.sub_category) for label in responses[0].labels] == [("meat", "beef")]

    stored_like = await recipe_repo.is_like("Carrot", user.pk)
    db_session.expunge_all()
    responses = [RecipeResponse.model_validate(stored) for stored in stored_like]
    assert [response.name for response in responses] == [recipe.name]
    assert [(label.category, label.sub_category) for label in responses[0].labels] == [("meat", "beef")]

    stored_plan = await plan_repo.update(
        PlannedDay(day=day, recipe=PlannedRecipe(pk=recipe.pk, name=recipe.name)), user.pk
    )
    db_session.expunge_all()
    assert PlannedDayResponse.model_validate(stored_plan).recipe == PlannedRecipe(pk=recipe.pk, name=recipe.name)

    stored_plans = await plan_repo.get_range(day, day, user.pk)
    db_session.expunge_all()
    responses = [PlannedDayResponse.model_validate(stored) for stored in stored_plans]
    assert [response.recipe for response in responses] == [PlannedRecipe(pk=recipe.pk, name=recipe.name)]


async def test_deleting_a_recipe_cascades_to_recipe_labels(db_session: AsyncSession, carrots_recipe):
    user = await UserRepository(db_session).create(CreateUserRequest(user_name="User One"))
    recipe = await RecipeRepository(db_session).create(carrots_recipe, user.pk)
    recipe.labels.append(StoredRecipeLabel(sub_category=SubCategory(name="beef", category=Category(name="meat"))))
    await db_session.flush()

    await db_session.delete(recipe)
    await db_session.flush()

    assert (await db_session.scalars(select(StoredRecipeLabel))).all() == []


async def test_deleting_a_category_cascades_to_sub_categories_and_recipe_labels(
    db_session: AsyncSession, carrots_recipe
):
    user = await UserRepository(db_session).create(CreateUserRequest(user_name="User One"))
    recipe = await RecipeRepository(db_session).create(carrots_recipe, user.pk)
    category = Category(name="meat")
    sub_category = SubCategory(name="beef", category=category)
    recipe.labels.append(StoredRecipeLabel(sub_category=sub_category))
    await db_session.flush()

    await db_session.delete(category)
    await db_session.flush()

    assert (await db_session.scalars(select(SubCategory))).all() == []
    assert (await db_session.scalars(select(StoredRecipeLabel))).all() == []


async def test_recipe_labels_require_an_existing_recipe_and_sub_category(db_session: AsyncSession):
    db_session.add(StoredRecipeLabel(recipe_pk=999, sub_category_pk=999))

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_sub_categories_require_an_existing_category(db_session: AsyncSession):
    db_session.add(SubCategory(name="beef", category_pk=999))

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_recipe_labels_are_unique_per_recipe_and_sub_category(db_session: AsyncSession, carrots_recipe):
    user = await UserRepository(db_session).create(CreateUserRequest(user_name="User One"))
    recipe = await RecipeRepository(db_session).create(carrots_recipe, user.pk)
    sub_category = SubCategory(name="beef", category=Category(name="meat"))
    recipe.labels.extend(
        [
            StoredRecipeLabel(sub_category=sub_category),
            StoredRecipeLabel(sub_category=sub_category),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_category_names_are_unique(db_session: AsyncSession):
    db_session.add_all([Category(name="meat"), Category(name="meat")])

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_sub_category_names_are_unique_within_a_category(db_session: AsyncSession):
    db_session.add(Category(name="meat", sub_categories=[SubCategory(name="stew"), SubCategory(name="stew")]))

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_the_same_sub_category_name_can_exist_in_different_categories(db_session: AsyncSession):
    db_session.add_all(
        [
            Category(name="meat", sub_categories=[SubCategory(name="stew")]),
            Category(name="fish", sub_categories=[SubCategory(name="stew")]),
        ]
    )
    await db_session.flush()

    assert len((await db_session.scalars(select(SubCategory))).all()) == 2


async def test_recipe_labels_are_ordered_by_sub_category_pk(db_session: AsyncSession, carrots_recipe):
    user = await UserRepository(db_session).create(CreateUserRequest(user_name="User One"))
    recipe = await RecipeRepository(db_session).create(carrots_recipe, user.pk)
    time_quick = SubCategory(name="quick", category=Category(name="time"))
    meat_beef = SubCategory(name="beef", category=Category(name="meat"))
    db_session.add_all([meat_beef, time_quick])
    await db_session.flush()
    recipe.labels.extend(
        [
            StoredRecipeLabel(sub_category=time_quick),
            StoredRecipeLabel(sub_category=meat_beef),
        ]
    )
    await db_session.flush()
    expected = [
        f"{sub_category.category.name}::{sub_category.name}"
        for sub_category in sorted([time_quick, meat_beef], key=lambda sub_category: sub_category.pk)
    ]
    db_session.expunge_all()

    stored = await RecipeRepository(db_session).get(recipe.pk, user.pk)
    assert stored is not None
    db_session.expunge_all()

    assert [str(label) for label in RecipeResponse.model_validate(stored).labels] == expected
