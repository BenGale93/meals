from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from meals.database.models import RecipeIngredient, StoredPlannedDay, StoredRecipe
from meals.schemas import PlannedRecipe

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
