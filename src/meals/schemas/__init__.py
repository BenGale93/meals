"""Pydantic schemas for the API, web views, CLI, and repositories.

The models are grouped by domain; this package re-exports them so import sites can keep using
``from meals.schemas import ...``.
"""

from meals.schemas.planner import (
    DayToPlan,
    PlannedDay,
    PlannedDayResponse,
    PlannedDays,
    PlannedRecipe,
    RecipeSummary,
)
from meals.schemas.recipes import (
    INGREDIENT_ERROR,
    NAME_FIRST_REGEX,
    QUANTITY,
    QUANTITY_FIRST_REGEX,
    CreateIngredientRequest,
    CreateRecipeRequest,
    CreateRecipes,
    IngredientResponse,
    RecipeResponse,
    Recipes,
    UpdateRecipeRequest,
    check_unique_ingredient_names,
)
from meals.schemas.timings import RecipeStep, TimingsCreate, TimingsResponse, TimingSteps
from meals.schemas.users import CreateUserRequest, UserResponse

__all__ = [
    "INGREDIENT_ERROR",
    "NAME_FIRST_REGEX",
    "QUANTITY",
    "QUANTITY_FIRST_REGEX",
    "CreateIngredientRequest",
    "CreateRecipeRequest",
    "CreateRecipes",
    "CreateUserRequest",
    "DayToPlan",
    "IngredientResponse",
    "PlannedDay",
    "PlannedDayResponse",
    "PlannedDays",
    "PlannedRecipe",
    "RecipeResponse",
    "RecipeStep",
    "RecipeSummary",
    "Recipes",
    "TimingSteps",
    "TimingsCreate",
    "TimingsResponse",
    "UpdateRecipeRequest",
    "UserResponse",
    "check_unique_ingredient_names",
]
