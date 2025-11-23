"""Repository module for interacting with the database session."""

import typing as t

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sqlalchemy.orm import joinedload

from meals.database.models import (
    RecipeIngredient,
    StoredIngredient,
    StoredPlannedDay,
    StoredRecipe,
    StoredTimings,
    User,
)
from meals.database.session import get_db
from meals.exceptions import (
    RecipeAlreadyExistsError,
    RecipeDoesNotExistError,
    TimingAlreadyExistsError,
    UserAlreadyExistsError,
)

if t.TYPE_CHECKING:
    from datetime import date

    from meals.schemas import CreateRecipeRequest, CreateUserRequest, PlannedDay, TimingsCreate, UpdateRecipeRequest


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self.session = session

    async def create(self, user_data: CreateUserRequest) -> User:
        """Creates a new user or throws an error if the username is being used."""
        user_stmt = select(User).filter_by(user_name=user_data.user_name)

        stmt_result = await self.session.scalars(user_stmt)
        user = stmt_result.first()

        if user:
            raise UserAlreadyExistsError

        user = User(user_name=user_data.user_name)

        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_name(self, user_name: str) -> User | None:
        """Get the user by the user name."""
        user_stmt = select(User).filter_by(user_name=user_name)

        stmt_result = await self.session.scalars(user_stmt)
        return stmt_result.first()


def get_user_repo(session: AsyncSession = Depends(get_db)) -> UserRepository:  # noqa: B008
    """Gets the user repository using dependency injection."""
    return UserRepository(session)


UserRepo = t.Annotated[UserRepository, Depends(get_user_repo)]


class RecipeRepository:
    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self.session = session

    async def create(self, recipe_data: CreateRecipeRequest, user_pk: int) -> StoredRecipe:
        """Creates a new recipe throws an error."""
        recipe_stmt = select(StoredRecipe).filter_by(name=recipe_data.name, user_pk=user_pk)

        stmt_result = await self.session.scalars(recipe_stmt)
        recipe = stmt_result.first()

        if recipe:
            raise RecipeAlreadyExistsError

        stored_recipe = StoredRecipe(name=recipe_data.name, instructions=recipe_data.instructions, user_pk=user_pk)
        if len(recipe_data.ingredients) == 0:
            stored_recipe.ingredients = []

        with self.session.no_autoflush:
            for ing in recipe_data.ingredients:
                ing_stmt = select(StoredIngredient).filter_by(name=ing.name)
                ing_stmt_result = await self.session.scalars(ing_stmt)
                ingredient = ing_stmt_result.first()
                if not ingredient:
                    ingredient = StoredIngredient(name=ing.name)
                    self.session.add(ingredient)
                stored_recipe.ingredients.append(
                    RecipeIngredient(ingredient=ingredient, quantity=ing.quantity, unit=ing.unit)
                )

        self.session.add(stored_recipe)
        await self.session.flush()
        return stored_recipe

    async def get(self, pk: int, user_pk: int) -> StoredRecipe | None:
        """Get the recipe by the primary key."""
        stmt = select(StoredRecipe).filter_by(pk=pk, user_pk=user_pk)
        stmt_result = await self.session.scalars(stmt)
        return stmt_result.first()

    async def get_by_name(self, name: str, user_pk: int) -> StoredRecipe | None:
        """Gets the recipe with a given name."""
        stmt = (
            select(StoredRecipe)
            .filter_by(name=name, user_pk=user_pk)
            .limit(1)
            .options(joinedload(StoredRecipe.ingredients).subqueryload(RecipeIngredient.ingredient))
        )
        stmt_result = await self.session.scalars(stmt)
        recipe = stmt_result.first()

        if recipe is None:
            return None

        return recipe

    async def get_all(self, user_pk: int, *, has_ingredients: bool = True) -> list[StoredRecipe]:
        """Gets all the recipes.

        Args:
            user_pk: The primary key of the user the recipe belong to.
            has_ingredients: Whether to only get recipe that have some ingredients.
        """
        stmt = (
            select(StoredRecipe)
            .filter_by(user_pk=user_pk)
            .options(joinedload(StoredRecipe.ingredients).subqueryload(RecipeIngredient.ingredient))
            .order_by(StoredRecipe.name)
        )
        stmt_result = await self.session.scalars(stmt)

        recipes = list(stmt_result.unique().fetchall())

        if has_ingredients:
            return [r for r in recipes if len(r.ingredients) > 0]
        return recipes

    async def update(self, recipe_data: UpdateRecipeRequest, user_pk: int) -> StoredRecipe:
        """Update an existing recipe."""
        existing_recipe = await self.get(recipe_data.pk, user_pk=user_pk)

        if existing_recipe is None:
            raise RecipeDoesNotExistError

        existing_recipe.name = recipe_data.name
        existing_recipe.instructions = recipe_data.instructions

        existing_ingredient_names = {i.ingredient.name for i in existing_recipe.ingredients}
        new_ingredient_names = {i.name for i in recipe_data.ingredients}

        to_delete = existing_ingredient_names - new_ingredient_names
        to_add = new_ingredient_names - existing_ingredient_names
        to_update = existing_ingredient_names | new_ingredient_names

        for existing in existing_recipe.ingredients:
            if existing.ingredient.name not in to_update:  # pragma: no cover # Not possible
                continue
            new_i = recipe_data.get_ingredient(existing.ingredient.name)
            if new_i is not None:
                existing.quantity = new_i.quantity
                existing.unit = new_i.unit

        existing_recipe.ingredients = [i for i in existing_recipe.ingredients if i.ingredient.name not in to_delete]

        for new in to_add:
            new_i = recipe_data.get_ingredient(new)
            if new_i is None:  # pragma: no cover # Not possible
                continue
            ing_stmt = select(StoredIngredient).filter_by(name=new_i.name)
            ing_stmt_result = await self.session.scalars(ing_stmt)
            ingredient = ing_stmt_result.first()
            if not ingredient:
                ingredient = StoredIngredient(name=new_i.name)
                self.session.add(ingredient)
            existing_recipe.ingredients.append(
                RecipeIngredient(ingredient=ingredient, quantity=new_i.quantity, unit=new_i.unit)
            )
        await self.session.flush()
        return existing_recipe

    async def is_like(self, snippet: str, user_pk: int) -> list[StoredRecipe]:
        """Gets any recipes that are like the snippet given."""
        stmt = (
            select(StoredRecipe)
            .filter(StoredRecipe.name.ilike(f"%{snippet}%"), StoredRecipe.user_pk == user_pk)
            .options(joinedload(StoredRecipe.ingredients).subqueryload(RecipeIngredient.ingredient))
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

    async def create(self, timings_data: TimingsCreate, user_pk: int) -> StoredTimings:
        """Creates a new timing."""
        timing_stmt = select(StoredTimings).filter_by(user_pk=user_pk)

        stmt_result = await self.session.scalars(timing_stmt)
        timing = stmt_result.first()

        if timing:
            raise TimingAlreadyExistsError

        stored_timings = StoredTimings(
            steps=timings_data.steps.model_dump_json(), finish_time=timings_data.finish_time, user_pk=user_pk
        )

        self.session.add(stored_timings)
        await self.session.flush()
        return stored_timings

    async def get(self, user_pk: int) -> StoredTimings | None:
        """Get the timing."""
        timing_stmt = select(StoredTimings).filter_by(user_pk=user_pk)

        stmt_result = await self.session.scalars(timing_stmt)
        return stmt_result.first()

    async def update(self, timings_data: TimingsCreate, user_pk: int) -> StoredTimings:
        """Updates a timing or creates it if it doesn't exist."""
        timing_stmt = select(StoredTimings).filter_by(user_pk=user_pk)

        stmt_result = await self.session.scalars(timing_stmt)
        timing = stmt_result.first()

        if not timing:
            timing = StoredTimings(
                steps=timings_data.steps.model_dump_json(), finish_time=timings_data.finish_time, user_pk=user_pk
            )
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


class PlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self.session = session

    async def update(self, planned_day: PlannedDay, user_pk: int) -> StoredPlannedDay:
        """Update the planned day."""
        stmt = select(StoredPlannedDay).filter_by(day=planned_day.day, user_pk=user_pk).limit(1)

        stmt_result = await self.session.scalars(stmt)
        planned = stmt_result.first()

        if planned is None:
            planned = StoredPlannedDay(day=planned_day.day, user_pk=user_pk)
            self.session.add(planned)

        planned.recipe_pk = planned_day.recipe.pk

        await self.session.flush()

        stmt = (
            select(StoredPlannedDay)
            .filter_by(pk=planned.pk, user_pk=user_pk)
            .options(joinedload(StoredPlannedDay.recipe))
        )
        refreshed_plan = await self.session.scalars(stmt)
        return refreshed_plan.one()

    async def get_range(self, start_date: date, end_date: date, user_pk: int) -> list[StoredPlannedDay]:
        """Get the meal plans between the two dates."""
        stmt = (
            select(StoredPlannedDay)
            .filter(StoredPlannedDay.day.between(start_date, end_date), StoredPlannedDay.user_pk == user_pk)
            .options(joinedload(StoredPlannedDay.recipe))
        )
        stmt_result = await self.session.scalars(stmt)
        return list(stmt_result.fetchall())

    async def summarise(self, user_pk: int) -> list[tuple[str, int, date | None]]:
        """Summarise past meals."""
        stmt = (
            select(
                StoredRecipe.name,
                func.count(StoredPlannedDay.pk),
                func.max(StoredPlannedDay.day),
            )
            .filter_by(user_pk=user_pk)
            .join(StoredPlannedDay, isouter=True)
            .group_by(StoredRecipe.name)
            .order_by(StoredRecipe.name)
        )

        result = await self.session.execute(stmt)

        return list(result.fetchall())  # type: ignore [arg-type]


def get_plan_repo(session: AsyncSession = Depends(get_db)) -> PlanRepository:  # noqa: B008
    """Gets the plan repository using dependency injection."""
    return PlanRepository(session)


PlanRepo = t.Annotated[PlanRepository, Depends(get_plan_repo)]
