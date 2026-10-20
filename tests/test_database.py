import datetime as dt
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from meals.database.models import RecipeIngredient, StoredPlannedDay, StoredRecipe
from meals.database.repository import PlanRepository, RecipeRepository, UserRepository
from meals.schemas import (
    CreateUserRequest,
    PlannedDay,
    PlannedDayResponse,
    PlannedRecipe,
    RecipeResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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
