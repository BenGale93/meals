"""Repository module for interacting with the database session."""

import typing as t

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sqlalchemy.orm import joinedload

from meals.database.models import RecipeIngredient, StoredIngredient, StoredRecipe, StoredTimings
from meals.database.session import get_db
from meals.exceptions import RecipeAlreadyExistsError, TimingAlreadyExistsError

if t.TYPE_CHECKING:
    from meals.schemas import CreateRecipeRequest, TimingsCreate


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
            raise RecipeAlreadyExistsError

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
        """Get the recipe by the primary key."""
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


class TimingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self.session = session

    async def create(self, timings_data: TimingsCreate) -> StoredTimings:
        """Creates a new timing."""
        timing_stmt = select(StoredTimings)

        stmt_result = await self.session.scalars(timing_stmt)
        timing = stmt_result.first()

        if timing:
            raise TimingAlreadyExistsError

        stored_timings = StoredTimings(steps=timings_data.steps.model_dump_json(), finish_time=timings_data.finish_time)

        self.session.add(stored_timings)
        await self.session.flush()
        return stored_timings

    async def get(self) -> StoredTimings | None:
        """Get the timing."""
        timing_stmt = select(StoredTimings)

        stmt_result = await self.session.scalars(timing_stmt)
        return stmt_result.first()

    async def update(self, timings_data: TimingsCreate) -> StoredTimings:
        """Updates a timing or creates it if it doesn't exist."""
        timing_stmt = select(StoredTimings)

        stmt_result = await self.session.scalars(timing_stmt)
        timing = stmt_result.first()

        if not timing:
            timing = StoredTimings(steps=timings_data.steps.model_dump_json(), finish_time=timings_data.finish_time)
            self.session.add(timing)
        else:
            timing.finish_time = timings_data.finish_time
            timing.steps = timings_data.steps.model_dump_json()

        await self.session.flush()
        return timing


def get_timings_repo(session: AsyncSession = Depends(get_db)) -> TimingsRepository:  # noqa: B008
    """Gets the recipe repository using dependency injection."""
    return TimingsRepository(session)


TimingRepo = t.Annotated[TimingsRepository, Depends(get_timings_repo)]
