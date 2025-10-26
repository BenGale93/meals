"""Repository module for interacting with the database session."""

import typing as t

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sqlalchemy.orm import joinedload

from meals.database.models import RecipeIngredient, StoredIngredient, StoredRecipe
from meals.database.session import get_db

if t.TYPE_CHECKING:
    from meals.schemas import CreateRecipeRequest


class RecipeRepository:
    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self.session = session

    async def create(self, recipe_data: CreateRecipeRequest) -> StoredRecipe:
        """Creates a new recipe or returns an existing one."""
        recipe_stmt = select(StoredRecipe).filter_by(name=recipe_data.name)

        stmt_result = await self.session.scalars(recipe_stmt)
        recipe = stmt_result.first()

        if recipe:
            return recipe

        stored_recipe = StoredRecipe(name=recipe_data.name, instructions=recipe_data.instructions)

        for ing in recipe_data.ingredients:
            ing_stmt = select(StoredIngredient).filter_by(name=ing.name)
            ing_stmt_result = await self.session.scalars(ing_stmt)
            ingredient = ing_stmt_result.first()
            if not ingredient:
                ingredient = StoredIngredient(name=ing.name)
                self.session.add(ingredient)
                await self.session.flush()
            stored_recipe.ingredients.append(
                RecipeIngredient(ingredient=ingredient, quantity=ing.quantity, unit=ing.unit)
            )

        self.session.add(stored_recipe)
        await self.session.flush()
        return stored_recipe

    async def get(self, pk: int) -> StoredRecipe | None:
        """Get the recipe by then primary key."""
        return await self.session.get(StoredRecipe, pk)

    async def get_by_name(self, name: str) -> StoredRecipe | None:
        """Gets the recipe with a given name."""
        stmt = (
            select(StoredRecipe)
            .filter_by(name=name)
            .limit(1)
            .options(joinedload(StoredRecipe.ingredients).subqueryload(RecipeIngredient.ingredient))
        )
        stmt_result = await self.session.scalars(stmt)
        recipe = stmt_result.first()

        if recipe is None:
            return None

        return recipe

    async def get_all(self) -> list[StoredRecipe]:
        """Gets all the recipes."""
        stmt = select(StoredRecipe).options(
            joinedload(StoredRecipe.ingredients).subqueryload(RecipeIngredient.ingredient)
        )
        stmt_result = await self.session.scalars(stmt)

        return list(stmt_result.unique().fetchall())


def get_recipe_repo(session: AsyncSession = Depends(get_db)) -> RecipeRepository:  # noqa: B008
    """Gets the recipe repository using dependency injection."""
    return RecipeRepository(session)


RecipeRepo = t.Annotated[RecipeRepository, Depends(get_recipe_repo)]
