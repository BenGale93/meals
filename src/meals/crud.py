"""The CRUD functions for interacting with the database."""

import typing as t

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from meals.schemas import Recipe, Recipes
from meals.tables import RecipeIngredient, StoredIngredient, StoredRecipe

if t.TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_recipes(db: AsyncSession, recipe_data: Recipe) -> StoredRecipe:
    """Creates a new recipe or returns an existing one."""
    recipe_stmt = select(StoredRecipe).filter_by(name=recipe_data.name)

    recipe = (await db.scalars(recipe_stmt)).first()

    if recipe:
        return recipe

    stored_recipe = StoredRecipe(name=recipe_data.name, instructions=recipe_data.instructions)

    for ing in recipe_data.ingredients:
        ingredient = (await db.scalars(select(StoredIngredient).filter_by(name=ing.name))).first()
        if not ingredient:
            ingredient = StoredIngredient(name=ing.name)
            db.add(ingredient)
            await db.flush()
        stored_recipe.ingredients.append(RecipeIngredient(ingredient=ingredient, quantity=ing.quantity, unit=ing.unit))

    db.add(stored_recipe)
    await db.commit()
    await db.refresh(stored_recipe)
    return stored_recipe


async def get_recipe(db: AsyncSession, name: str) -> Recipe | None:
    """Gets the recipe with a given name."""
    stmt = (
        select(StoredRecipe)
        .filter_by(name=name)
        .limit(1)
        .options(joinedload(StoredRecipe.ingredients).subqueryload(RecipeIngredient.ingredient))
    )
    recipe = (await db.scalars(stmt)).first()

    if recipe is None:
        return None

    return Recipe.model_validate(recipe)


async def get_all_recipes(db: AsyncSession) -> Recipes:
    """Gets all the recipes."""
    stmt = select(StoredRecipe).options(joinedload(StoredRecipe.ingredients).subqueryload(RecipeIngredient.ingredient))
    recipes = (await db.scalars(stmt)).unique().fetchall()

    return Recipes.model_validate(recipes)
