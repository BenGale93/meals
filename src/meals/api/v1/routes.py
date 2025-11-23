"""The routes for the data API."""

from datetime import date  # noqa: TC003

from fastapi import APIRouter, HTTPException, status

from meals import schemas
from meals.auth import CurrentUser  # noqa: TC001
from meals.database.repository import PlanRepo, RecipeRepo, TimingRepo, UserRepo  # noqa: TC001
from meals.exceptions import (
    RecipeAlreadyExistsError,
    RecipeDoesNotExistError,
    TimingAlreadyExistsError,
    UserAlreadyExistsError,
)

router = APIRouter(prefix="/v1", tags=["v1"])


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(data: schemas.CreateUserRequest, repo: UserRepo) -> schemas.UserResponse:
    """Creates the user in the given database."""
    try:
        new_user = await repo.create(data)
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message) from None
    return schemas.UserResponse.model_validate(new_user)


@router.get("/users/me")
async def read_users_me(current_user: CurrentUser) -> schemas.UserResponse:
    """Reads the current user."""
    return current_user


@router.post("/recipes", status_code=status.HTTP_201_CREATED)
async def create_recipe(
    data: schemas.CreateRecipeRequest, repo: RecipeRepo, user: CurrentUser
) -> schemas.RecipeResponse:
    """Creates the recipe in the given database."""
    try:
        new_recipe = await repo.create(data, user_pk=user.pk)
    except RecipeAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message) from None

    return schemas.RecipeResponse.model_validate(new_recipe)


@router.get("/recipes", status_code=status.HTTP_200_OK)
async def get_recipes(repo: RecipeRepo, user: CurrentUser, *, has_ingredients: bool = True) -> schemas.Recipes:
    """Get all the recipe in the database."""
    recipes = await repo.get_all(user_pk=user.pk, has_ingredients=has_ingredients)

    return schemas.Recipes.model_validate(recipes)


@router.get("/recipes/{pk}", status_code=status.HTTP_200_OK)
async def get_recipe_by_key(pk: int, repo: RecipeRepo, user: CurrentUser) -> schemas.RecipeResponse:
    """Get the recipe by the primary key of that recipe."""
    recipe = await repo.get(pk, user_pk=user.pk)

    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe does not exist.")

    return schemas.RecipeResponse.model_validate(recipe)


@router.get("/recipes/", status_code=status.HTTP_200_OK)
async def get_recipe(name: str, repo: RecipeRepo, user: CurrentUser) -> schemas.RecipeResponse:
    """Get a recipe by name."""
    recipe = await repo.get_by_name(name, user_pk=user.pk)

    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recipe named '{name}' does not exist.")

    return schemas.RecipeResponse.model_validate(recipe)


@router.put("/recipes", status_code=status.HTTP_200_OK)
async def update_recipe(
    data: schemas.UpdateRecipeRequest, repo: RecipeRepo, user: CurrentUser
) -> schemas.RecipeResponse:
    """Update an existing recipe."""
    try:
        recipe = await repo.update(data, user_pk=user.pk)
    except RecipeDoesNotExistError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from None

    return schemas.RecipeResponse.model_validate(recipe)


@router.get("/recipes/like/", status_code=status.HTTP_200_OK)
async def get_recipe_like(snippet: str, repo: RecipeRepo, user: CurrentUser) -> schemas.Recipes:
    """Get a recipe by snippet."""
    recipes = await repo.is_like(snippet, user_pk=user.pk)

    return schemas.Recipes.model_validate(recipes)


@router.post("/timings", status_code=status.HTTP_201_CREATED)
async def create_timings(data: schemas.TimingsCreate, repo: TimingRepo, user: CurrentUser) -> schemas.TimingsResponse:
    """Creates the timings in the given database."""
    try:
        new_timings = await repo.create(data, user_pk=user.pk)
    except TimingAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message) from None

    steps = schemas.TimingSteps.model_validate_json(new_timings.steps)

    return schemas.TimingsResponse(pk=new_timings.pk, steps=steps, finish_time=new_timings.finish_time)


@router.get("/timings", status_code=status.HTTP_200_OK)
async def get_timings(repo: TimingRepo, user: CurrentUser) -> schemas.TimingsResponse:
    """Get the timings by the primary key of that timing."""
    timings = await repo.get(user_pk=user.pk)

    if timings is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timing does not exist.")

    steps = schemas.TimingSteps.model_validate_json(timings.steps)

    return schemas.TimingsResponse(pk=timings.pk, steps=steps, finish_time=timings.finish_time)


@router.patch("/timings", status_code=status.HTTP_200_OK)
async def update_timings(
    timings_data: schemas.TimingsCreate, repo: TimingRepo, user: CurrentUser
) -> schemas.TimingsResponse:
    """Get the timings by the primary key of that timing."""
    timings = await repo.update(timings_data, user_pk=user.pk)

    steps = schemas.TimingSteps.model_validate_json(timings.steps)

    return schemas.TimingsResponse(pk=timings.pk, steps=steps, finish_time=timings.finish_time)


@router.post("/planned_day", status_code=status.HTTP_201_CREATED)
async def update_planned_day(data: schemas.PlannedDay, repo: PlanRepo, user: CurrentUser) -> schemas.PlannedDayResponse:
    """Update the planned day."""
    new_plan = await repo.update(data, user_pk=user.pk)

    return schemas.PlannedDayResponse.model_validate(new_plan)


@router.get("/planned_day", status_code=status.HTTP_200_OK)
async def get_plans(
    start_date: date, end_date: date, repo: PlanRepo, user: CurrentUser
) -> list[schemas.PlannedDayResponse]:
    """Get the plans over the given range."""
    planned_days = await repo.get_range(start_date, end_date, user_pk=user.pk)

    return [schemas.PlannedDayResponse.model_validate(d) for d in planned_days]


@router.get("/planned_day/summary/", status_code=status.HTTP_200_OK)
async def plan_summary(repo: PlanRepo, user: CurrentUser) -> list[schemas.RecipeSummary]:
    """Get the plans over the given range."""
    summary = await repo.summarise(user_pk=user.pk)

    return [schemas.RecipeSummary(name=s[0], count=s[1], last_eaten=s[2]) for s in summary]
