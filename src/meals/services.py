"""Use cases shared by the JSON API and the HTML views.

The HTTP layers should stay thin: they only translate between requests/responses and these
services, which own the recipe, planner, and timing rules and talk to the repositories. Keeping
the rules here means the API and the web views cannot drift apart (bug 7 was a symptom of that).
"""

import typing as t
from datetime import date, timedelta

from fastapi import Depends

from meals.database.repository import PlanRepo, RecipeRepo, TimingRepo  # noqa: TC001
from meals.exceptions import RecipeDoesNotExistError
from meals.schemas import (
    CreateRecipeRequest,
    DayToPlan,
    LabelResponse,
    Labels,
    PlannedDay,
    PlannedDayResponse,
    PlannedDays,
    PlannedRecipe,
    RecipeResponse,
    Recipes,
    RecipeSummary,
    TimingsCreate,
    TimingsResponse,
    TimingSteps,
    UpdateRecipeRequest,
)

if t.TYPE_CHECKING:
    from meals.database.models import StoredTimings
    from meals.database.repository import PlanRepository, RecipeRepository, TimingsRepository
    from meals.schemas import LabelFilter


class RecipeService:
    """Use cases for recipes."""

    def __init__(self, repo: RecipeRepository) -> None:
        """Initialise with a recipe repository."""
        self._repo = repo

    async def list(
        self, user_pk: int, *, has_ingredients: bool = True, label_filter: LabelFilter | None = None
    ) -> Recipes:
        """Return the user's recipes, optionally filtered by labels."""
        recipes = await self._repo.get_all(user_pk, has_ingredients=has_ingredients, label_filter=label_filter)
        return Recipes.model_validate(recipes)

    async def labels(self) -> Labels:
        """Return the full label taxonomy."""
        sub_categories = await self._repo.get_labels()
        return Labels(
            [
                LabelResponse(category=sub_category.category.name, sub_category=sub_category.name)
                for sub_category in sub_categories
            ]
        )

    async def get(self, pk: int, user_pk: int) -> RecipeResponse:
        """Return a recipe by primary key, or raise `RecipeDoesNotExistError`."""
        recipe = await self._repo.get(pk, user_pk)
        if recipe is None:
            raise RecipeDoesNotExistError
        return RecipeResponse.model_validate(recipe)

    async def get_by_name(self, name: str, user_pk: int) -> RecipeResponse:
        """Return a recipe by name, or raise `RecipeDoesNotExistError`."""
        recipe = await self._repo.get_by_name(name, user_pk)
        if recipe is None:
            msg = f"Recipe named '{name}' does not exist."
            raise RecipeDoesNotExistError(msg)
        return RecipeResponse.model_validate(recipe)

    async def like(self, snippet: str, user_pk: int) -> Recipes:
        """Return the user's recipes whose name matches the snippet."""
        recipes = await self._repo.is_like(snippet, user_pk)
        return Recipes.model_validate(recipes)

    async def create(self, data: CreateRecipeRequest, user_pk: int) -> RecipeResponse:
        """Create a recipe."""
        return RecipeResponse.model_validate(await self._repo.create(data, user_pk))

    async def update(self, data: UpdateRecipeRequest, user_pk: int) -> RecipeResponse:
        """Update a recipe."""
        return RecipeResponse.model_validate(await self._repo.update(data, user_pk))


def get_recipe_service(repo: RecipeRepo) -> RecipeService:
    """FastAPI dependency that builds a `RecipeService`."""
    return RecipeService(repo)


RecipeServiceDep = t.Annotated[RecipeService, Depends(get_recipe_service)]


class PlanService:
    """Use cases for the meal plan."""

    def __init__(self, plan_repo: PlanRepository, recipe_repo: RecipeRepository) -> None:
        """Initialise with the plan and recipe repositories."""
        self._plan_repo = plan_repo
        self._recipe_repo = recipe_repo

    async def get_range(self, start_date: date, end_date: date, user_pk: int) -> list[PlannedDayResponse]:
        """Return the meals planned between two dates."""
        planned_days = await self._plan_repo.get_range(start_date, end_date, user_pk)
        return [PlannedDayResponse.model_validate(day) for day in planned_days]

    async def summary(self, user_pk: int, label_filter: LabelFilter | None = None) -> list[RecipeSummary]:
        """Return a summary of the meals eaten so far, optionally filtered by labels."""
        summary = await self._plan_repo.summarise(user_pk, label_filter=label_filter)
        return [RecipeSummary(name=name, count=count, last_eaten=last_eaten) for name, count, last_eaten in summary]

    async def plan(self, data: PlannedDay, user_pk: int) -> PlannedDayResponse:
        """Plan one of the user's recipes on a day."""
        recipe = await self._recipe_repo.get(data.recipe.pk, user_pk)
        if recipe is None:
            raise RecipeDoesNotExistError
        return PlannedDayResponse.model_validate(await self._plan_repo.update(data, user_pk))

    async def plan_by_meal_name(self, meal: str, day: date, user_pk: int) -> PlannedDayResponse | None:
        """Plan the recipe matching a meal name, or return `None` if there is no such recipe."""
        recipe = await self._recipe_repo.get_by_name(meal, user_pk)
        if recipe is None:
            return None
        return await self.plan(PlannedDay(day=day, recipe=PlannedRecipe(pk=recipe.pk, name=recipe.name)), user_pk)

    async def week(self, user_pk: int) -> PlannedDays:
        """Return the seven day plan starting today."""
        today = date.today()
        raw_plan = await self._plan_repo.get_range(today, today + timedelta(days=7), user_pk)

        days_to_plan: list[DayToPlan] = []
        for i in range(7):
            day = today + timedelta(days=i)
            planned_day = DayToPlan(day=day, recipe=None)
            for raw_day in raw_plan:
                if day != raw_day.day:
                    continue
                planned_day.recipe = PlannedRecipe(pk=raw_day.recipe_pk, name=raw_day.recipe.name)
                break
            days_to_plan.append(planned_day)

        return PlannedDays(days_to_plan)


def get_plan_service(plan_repo: PlanRepo, recipe_repo: RecipeRepo) -> PlanService:
    """FastAPI dependency that builds a `PlanService`."""
    return PlanService(plan_repo, recipe_repo)


PlanServiceDep = t.Annotated[PlanService, Depends(get_plan_service)]


class TimingsService:
    """Use cases for roast timings."""

    def __init__(self, repo: TimingsRepository) -> None:
        """Initialise with a timings repository."""
        self._repo = repo

    async def get(self, user_pk: int) -> TimingsResponse | None:
        """Return the user's timings, or `None` if they have not set any."""
        timings = await self._repo.get(user_pk)
        if timings is None:
            return None
        return self._to_response(timings)

    async def create(self, data: TimingsCreate, user_pk: int) -> TimingsResponse:
        """Create the timings."""
        return self._to_response(await self._repo.create(data, user_pk))

    async def update(self, data: TimingsCreate, user_pk: int) -> TimingsResponse:
        """Create or update the timings."""
        return self._to_response(await self._repo.update(data, user_pk))

    @staticmethod
    def _to_response(timings: StoredTimings) -> TimingsResponse:
        """Convert stored timings into the response model."""
        steps = TimingSteps.model_validate_json(timings.steps)
        return TimingsResponse(pk=timings.pk, steps=steps, finish_time=timings.finish_time)


def get_timings_service(repo: TimingRepo) -> TimingsService:
    """FastAPI dependency that builds a `TimingsService`."""
    return TimingsService(repo)


TimingsServiceDep = t.Annotated[TimingsService, Depends(get_timings_service)]
