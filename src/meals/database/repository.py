"""Repository module for interacting with the database session."""

import typing as t
from datetime import date

from fastapi import Depends
from sqlalchemy import distinct, func, select, tuple_
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
    from sqlalchemy import Select

    from meals.schemas import (
        CreateLabel,
        CreateRecipeRequest,
        CreateUserRequest,
        LabelFilter,
        PlannedDay,
        TimingsCreate,
        UpdateRecipeRequest,
    )

# Response models are serialised from these ORM objects after the query, so every
# relationship they touch must already be loaded: an implicit async lazy load raises
# MissingGreenlet (a 500). Keep these tuples complete and pass them to every query that
# can return an object a response model will serialise.
#
# `RecipeResponse` serialises recipe.ingredients and each row's ingredient, plus
# recipe.labels and each label's sub-category and category.
RECIPE_LOAD_OPTIONS = (
    joinedload(StoredRecipe.ingredients).subqueryload(RecipeIngredient.ingredient),
    joinedload(StoredRecipe.labels).subqueryload(StoredRecipeLabel.sub_category).subqueryload(SubCategory.category),
)
# `PlannedDayResponse` serialises planned.recipe.
PLANNED_DAY_LOAD_OPTIONS = (joinedload(StoredPlannedDay.recipe),)


def _matching_recipe_pks(label_filter: LabelFilter) -> Select[int]:
    """Build the subquery of recipe pks that satisfy a label filter.

    A recipe needs at least one matching sub-category in every requested category, which
    gives OR within a category and AND across categories.
    """
    pairs = [
        (category, sub_category)
        for category, sub_categories in label_filter.groups.items()
        for sub_category in sub_categories
    ]
    return (
        select(StoredRecipeLabel.recipe_pk)
        .join(SubCategory, SubCategory.pk == StoredRecipeLabel.sub_category_pk)
        .join(Category, Category.pk == SubCategory.category_pk)
        .where(tuple_(Category.name, SubCategory.name).in_(pairs))
        .group_by(StoredRecipeLabel.recipe_pk)
        .having(func.count(distinct(Category.pk)) == label_filter.category_count)
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
        label_pks = await self._resolve_label_pks(recipe_data.labels)
        recipe_pk = stored_recipe.pk
        for sub_category_pk in label_pks:
            self.session.add(StoredRecipeLabel(recipe_pk=recipe_pk, sub_category_pk=sub_category_pk))
        await self.session.flush()
        self.session.expire(stored_recipe)
        return t.cast("StoredRecipe", await self.get(recipe_pk, user_pk))

    async def _resolve_label_pks(self, labels: list[CreateLabel]) -> set[int]:
        """Upsert the requested labels and return their deduplicated sub-category pks."""
        if not labels:
            return set()

        category_names = {label.category for label in labels}
        categories = {
            category.name: category
            for category in (
                await self.session.scalars(select(Category).where(Category.name.in_(category_names)))
            ).all()
        }
        for category_name in category_names - categories.keys():
            category = Category(name=category_name)
            self.session.add(category)
            categories[category_name] = category

        sub_categories = {
            (sub_category.category.name, sub_category.name): sub_category
            for sub_category in (
                await self.session.scalars(
                    select(SubCategory)
                    .join(SubCategory.category)
                    .where(Category.name.in_(category_names))
                    .options(joinedload(SubCategory.category))
                )
            ).all()
        }
        for label in labels:
            key = (label.category, label.sub_category)
            if key not in sub_categories:
                sub_category = SubCategory(name=label.sub_category, category=categories[label.category])
                self.session.add(sub_category)
                sub_categories[key] = sub_category

        await self.session.flush()
        return {sub_categories[(label.category, label.sub_category)].pk for label in labels}

    async def get_labels(self) -> list[SubCategory]:
        """Get the full label taxonomy, sorted by category and sub-category."""
        stmt = (
            select(SubCategory)
            .join(SubCategory.category)
            .options(joinedload(SubCategory.category))
            .order_by(Category.name, SubCategory.name)
        )
        stmt_result = await self.session.scalars(stmt)
        return list(stmt_result.all())

    async def get(self, pk: int, user_pk: int) -> StoredRecipe | None:
        """Get the recipe by the primary key."""
        stmt = select(StoredRecipe).filter_by(pk=pk, user_pk=user_pk).options(*RECIPE_LOAD_OPTIONS)
        stmt_result = await self.session.scalars(stmt)
        return stmt_result.first()

    async def get_by_name(self, name: str, user_pk: int) -> StoredRecipe | None:
        """Gets the recipe with a given name."""
        stmt = select(StoredRecipe).filter_by(name=name, user_pk=user_pk).limit(1).options(*RECIPE_LOAD_OPTIONS)
        stmt_result = await self.session.scalars(stmt)
        recipe = stmt_result.first()

        if recipe is None:
            return None

        return recipe

    async def get_all(
        self,
        user_pk: int,
        *,
        has_ingredients: bool = True,
        label_filter: LabelFilter | None = None,
    ) -> list[StoredRecipe]:
        """Gets all the recipes.

        Args:
            user_pk: The primary key of the user the recipe belong to.
            has_ingredients: Whether to only get recipe that have some ingredients.
            label_filter: Optional label filter to apply.
        """
        stmt = select(StoredRecipe).filter_by(user_pk=user_pk).options(*RECIPE_LOAD_OPTIONS).order_by(StoredRecipe.name)
        if label_filter:
            stmt = stmt.where(StoredRecipe.pk.in_(_matching_recipe_pks(label_filter)))
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

        name_stmt = select(StoredRecipe).filter_by(name=recipe_data.name, user_pk=user_pk)
        stmt_result = await self.session.scalars(name_stmt)
        conflicting_recipe = stmt_result.first()

        if conflicting_recipe is not None and conflicting_recipe.pk != existing_recipe.pk:
            raise RecipeAlreadyExistsError

        existing_recipe.name = recipe_data.name
        existing_recipe.instructions = recipe_data.instructions

        new_ingredients = {i.name: i for i in recipe_data.ingredients}
        existing_ingredient_names = {i.ingredient.name for i in existing_recipe.ingredients}

        to_delete = existing_ingredient_names - new_ingredients.keys()
        to_add = new_ingredients.keys() - existing_ingredient_names

        for existing in existing_recipe.ingredients:
            new_i = new_ingredients.get(existing.ingredient.name)
            if new_i is not None:
                existing.quantity = new_i.quantity
                existing.unit = new_i.unit

        existing_recipe.ingredients = [i for i in existing_recipe.ingredients if i.ingredient.name not in to_delete]

        for new in to_add:
            new_i = new_ingredients[new]
            ing_stmt = select(StoredIngredient).filter_by(name=new_i.name)
            ing_stmt_result = await self.session.scalars(ing_stmt)
            ingredient = ing_stmt_result.first()
            if not ingredient:
                ingredient = StoredIngredient(name=new_i.name)
                self.session.add(ingredient)
            existing_recipe.ingredients.append(
                RecipeIngredient(ingredient=ingredient, quantity=new_i.quantity, unit=new_i.unit)
            )

        existing_labels = list(existing_recipe.labels)
        recipe_pk = existing_recipe.pk
        new_label_pks = await self._resolve_label_pks(recipe_data.labels)
        existing_label_pks = {label.sub_category_pk for label in existing_labels}
        for label in existing_labels:
            if label.sub_category_pk not in new_label_pks:
                await self.session.delete(label)
        for sub_category_pk in new_label_pks - existing_label_pks:
            self.session.add(StoredRecipeLabel(recipe_pk=recipe_pk, sub_category_pk=sub_category_pk))

        await self.session.flush()
        self.session.expire(existing_recipe)
        return t.cast("StoredRecipe", await self.get(recipe_pk, user_pk))

    async def is_like(self, snippet: str, user_pk: int) -> list[StoredRecipe]:
        """Gets any recipes that are like the snippet given."""
        stmt = (
            select(StoredRecipe)
            .filter(StoredRecipe.name.ilike(f"%{snippet}%"), StoredRecipe.user_pk == user_pk)
            .options(*RECIPE_LOAD_OPTIONS)
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

        stmt = select(StoredPlannedDay).filter_by(pk=planned.pk, user_pk=user_pk).options(*PLANNED_DAY_LOAD_OPTIONS)
        refreshed_plan = await self.session.scalars(stmt)
        return refreshed_plan.one()

    async def get_range(self, start_date: date, end_date: date, user_pk: int) -> list[StoredPlannedDay]:
        """Get the meal plans between the two dates."""
        stmt = (
            select(StoredPlannedDay)
            .filter(StoredPlannedDay.day.between(start_date, end_date), StoredPlannedDay.user_pk == user_pk)
            .options(*PLANNED_DAY_LOAD_OPTIONS)
        )
        stmt_result = await self.session.scalars(stmt)
        return list(stmt_result.fetchall())

    async def summarise(
        self, user_pk: int, label_filter: LabelFilter | None = None
    ) -> list[tuple[str, int, date | None]]:
        """Summarise meals that have already been eaten."""
        stmt = (
            select(
                StoredRecipe.name,
                func.count(StoredPlannedDay.pk),
                func.max(StoredPlannedDay.day),
            )
            .where(StoredRecipe.user_pk == user_pk)
            .join(
                StoredPlannedDay,
                (StoredPlannedDay.recipe_pk == StoredRecipe.pk)
                & (StoredPlannedDay.user_pk == user_pk)
                & (StoredPlannedDay.day <= date.today()),
                isouter=True,
            )
            .group_by(StoredRecipe.name)
            .order_by(StoredRecipe.name)
        )
        if label_filter:
            stmt = stmt.where(StoredRecipe.pk.in_(_matching_recipe_pks(label_filter)))

        result = await self.session.execute(stmt)

        return [(row[0], row[1], row[2]) for row in result.fetchall()]


def get_plan_repo(session: AsyncSession = Depends(get_db)) -> PlanRepository:  # noqa: B008
    """Gets the plan repository using dependency injection."""
    return PlanRepository(session)


PlanRepo = t.Annotated[PlanRepository, Depends(get_plan_repo)]
