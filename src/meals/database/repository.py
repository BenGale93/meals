"""Repository module for interacting with the database session."""

import typing as t

from fastapi import Depends
from sqlalchemy import Select, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sqlalchemy.orm import joinedload

from meals.database.models import (
    Category,
    RecipeIngredient,
    StoredIngredient,
    StoredPlannedDay,
    StoredRecipe,
    StoredRecipeLabel,
    StoredTimings,
    SubCategory,
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

    from meals.schemas import (
        CreateLabel,
        CreateRecipeRequest,
        CreateUserRequest,
        PlannedDay,
        TimingsCreate,
        UpdateRecipeRequest,
    )


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
        """Create a new recipe.

        Raises:
            RecipeAlreadyExistsError
        """
        result = await self.session.scalars(
            select(StoredRecipe).where(
                StoredRecipe.name == recipe_data.name,
                StoredRecipe.user_pk == user_pk,
            )
        )
        if result.first():
            raise RecipeAlreadyExistsError

        recipe = StoredRecipe(
            name=recipe_data.name,
            instructions=recipe_data.instructions,
            user_pk=user_pk,
        )

        self.session.add(recipe)
        await self.session.flush()

        for ing in recipe_data.ingredients:
            ing_result = await self.session.scalars(select(StoredIngredient).where(StoredIngredient.name == ing.name))
            ingredient = ing_result.first()

            if not ingredient:
                ingredient = StoredIngredient(name=ing.name)
                self.session.add(ingredient)
                await self.session.flush()

            self.session.add(
                RecipeIngredient(
                    recipe_pk=recipe.pk,
                    ingredient_pk=ingredient.pk,
                    quantity=ing.quantity,
                    unit=ing.unit,
                )
            )

        label_pks = await self._resolve_label_pks(
            [(label.category, label.sub_category) for label in recipe_data.labels]
        )

        for sub_pk in label_pks:
            self.session.add(
                StoredRecipeLabel(
                    recipe_pk=recipe.pk,
                    label_pk=sub_pk,
                )
            )

        await self.session.flush()

        stmt = self._join_fields(select(StoredRecipe).where(StoredRecipe.pk == recipe.pk))
        result = await self.session.scalars(stmt)
        return result.unique().one()

    async def get(self, pk: int, user_pk: int) -> StoredRecipe | None:
        """Get the recipe by the primary key."""
        stmt = self._join_fields(select(StoredRecipe).filter_by(pk=pk, user_pk=user_pk).limit(1))
        stmt_result = await self.session.scalars(stmt)
        return stmt_result.first()

    async def get_by_name(self, name: str, user_pk: int) -> StoredRecipe | None:
        """Gets the recipe with a given name."""
        stmt = self._join_fields(select(StoredRecipe).filter_by(name=name, user_pk=user_pk).limit(1))
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
        stmt = self._join_fields(select(StoredRecipe).filter_by(user_pk=user_pk)).order_by(StoredRecipe.name)
        stmt_result = await self.session.scalars(stmt)

        recipes = list(stmt_result.unique().fetchall())

        if has_ingredients:
            return [r for r in recipes if len(r.ingredients) > 0]
        return recipes

    async def update(self, recipe_data: UpdateRecipeRequest, user_pk: int) -> StoredRecipe:
        """Update an existing recipe."""
        recipe = await self.get(recipe_data.pk, user_pk)
        if recipe is None:
            raise RecipeDoesNotExistError

        recipe.name = recipe_data.name
        recipe.instructions = recipe_data.instructions

        # ---------- INGREDIENTS ----------
        existing = {(i.ingredient.name): i for i in recipe.ingredients}
        incoming = {ing.name: ing for ing in recipe_data.ingredients}

        # delete removed
        for name, ri in existing.items():
            if name not in incoming:
                await self.session.delete(ri)

        # update / insert
        for name, ing in incoming.items():
            if name in existing:
                ri = existing[name]
                ri.quantity = ing.quantity
                ri.unit = ing.unit
            else:
                result = await self.session.scalars(select(StoredIngredient).where(StoredIngredient.name == name))
                ingredient = result.first()
                if not ingredient:
                    ingredient = StoredIngredient(name=name)
                    self.session.add(ingredient)
                    await self.session.flush()

                self.session.add(
                    RecipeIngredient(
                        recipe_pk=recipe.pk,
                        ingredient_pk=ingredient.pk,
                        quantity=ing.quantity,
                        unit=ing.unit,
                    )
                )

        # ---------- LABELS ----------
        label_result = await self.session.scalars(
            select(StoredRecipeLabel).where(StoredRecipeLabel.recipe_pk == recipe.pk)
        )
        existing_labels = label_result.all()

        existing_label_map = {lbl.label_pk: lbl for lbl in existing_labels}

        incoming_label_pks = set(
            await self._resolve_label_pks([(label.category, label.sub_category) for label in recipe_data.labels])
        )

        existing_pks = set(existing_label_map.keys())

        for pk in existing_pks - incoming_label_pks:
            await self.session.delete(existing_label_map[pk])

        for pk in incoming_label_pks - existing_pks:
            self.session.add(
                StoredRecipeLabel(
                    recipe_pk=recipe.pk,
                    label_pk=pk,
                )
            )

        await self.session.flush()

        stmt = self._join_fields(select(StoredRecipe).where(StoredRecipe.pk == recipe.pk))
        recipe_result = await self.session.scalars(stmt)
        return recipe_result.unique().one()

    async def is_like(self, snippet: str, user_pk: int) -> list[StoredRecipe]:
        """Gets any recipes that are like the snippet given."""
        stmt = self._join_fields(
            select(StoredRecipe).filter(StoredRecipe.name.ilike(f"%{snippet}%"), StoredRecipe.user_pk == user_pk)
        )
        stmt_result = await self.session.scalars(stmt)

        return list(stmt_result.unique().fetchall())

    async def with_labels(self, labels: list[CreateLabel], user_pk: int) -> list[StoredRecipe]:
        """Gets all recipes with all of the given labels."""
        if not labels:  # pragma: no cover # The route guards against empty lists
            return []

        label_tuples = [(label.category, label.sub_category) for label in labels]

        stmt = (
            select(StoredRecipe)
            .filter(StoredRecipe.user_pk == user_pk)
            .join(StoredRecipe.labels)
            .join(StoredRecipeLabel.label)  # SubCategory
            .join(SubCategory.category)  # Category
            .where(tuple_(Category.name, SubCategory.name).in_(label_tuples))
            .group_by(StoredRecipe.pk)
            .having(func.count(func.distinct(SubCategory.pk)) == len(labels))
        )
        stmt = self._join_fields(stmt)
        stmt_result = await self.session.scalars(stmt)

        return list(stmt_result.unique().fetchall())

    @staticmethod
    def _join_fields(stmt: Select[tuple[StoredRecipe]]) -> Select[tuple[StoredRecipe]]:
        return (
            stmt.options(joinedload(StoredRecipe.ingredients).subqueryload(RecipeIngredient.ingredient))
            .options(
                joinedload(StoredRecipe.labels).subqueryload(StoredRecipeLabel.label).subqueryload(SubCategory.category)
            )
            .execution_options(populate_existing=True)
        )

    async def _resolve_label_pks(
        self,
        labels: list[tuple[str, str]],
    ) -> list[int]:
        sub_pks: list[int] = []

        for category_name, sub_name in labels:
            # CATEGORY
            result = await self.session.scalars(select(Category.pk).where(Category.name == category_name))
            category_pk = result.first()

            if category_pk is None:
                category = Category(name=category_name)
                self.session.add(category)
                await self.session.flush()
                category_pk = category.pk

            # SUB-CATEGORY
            result = await self.session.scalars(
                select(SubCategory.pk).where(
                    SubCategory.name == sub_name,
                    SubCategory.category_pk == category_pk,
                )
            )
            sub_pk = result.first()

            if sub_pk is None:
                sub = SubCategory(name=sub_name, category_pk=category_pk)
                self.session.add(sub)
                await self.session.flush()
                sub_pk = sub.pk

            sub_pks.append(sub_pk)

        return sub_pks


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
