"""The routes for the data API."""

from datetime import date  # noqa: TC003

from fastapi import APIRouter, HTTPException, status

from meals import schemas
from meals.auth import CurrentUser  # noqa: TC001
from meals.database.repository import UserRepo  # noqa: TC001
from meals.exceptions import (
    RecipeAlreadyExistsError,
    RecipeDoesNotExistError,
    TimingAlreadyExistsError,
    UserAlreadyExistsError,
)
from meals.services import PlanServiceDep, RecipeServiceDep, TimingsServiceDep  # noqa: TC001

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
    data: schemas.CreateRecipeRequest, service: RecipeServiceDep, user: CurrentUser
) -> schemas.RecipeResponse:
    """Creates the recipe in the given database."""
    try:
        return await service.create(data, user.pk)
    except RecipeAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message) from None


@router.get("/recipes", status_code=status.HTTP_200_OK)
async def get_recipes(service: RecipeServiceDep, user: CurrentUser, *, has_ingredients: bool = True) -> schemas.Recipes:
    """Get all the recipe in the database."""
    return await service.list(user.pk, has_ingredients=has_ingredients)


@router.get("/recipes/{pk}", status_code=status.HTTP_200_OK)
async def get_recipe_by_key(pk: int, service: RecipeServiceDep, user: CurrentUser) -> schemas.RecipeResponse:
    """Get the recipe by the primary key of that recipe."""
    try:
        return await service.get(pk, user.pk)
    except RecipeDoesNotExistError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from None


@router.get("/recipes/", status_code=status.HTTP_200_OK)
async def get_recipe(name: str, service: RecipeServiceDep, user: CurrentUser) -> schemas.RecipeResponse:
    """Get a recipe by name."""
    try:
        return await service.get_by_name(name, user.pk)
    except RecipeDoesNotExistError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from None


@router.put("/recipes", status_code=status.HTTP_200_OK)
async def update_recipe(
    data: schemas.UpdateRecipeRequest, service: RecipeServiceDep, user: CurrentUser
) -> schemas.RecipeResponse:
    """Update an existing recipe."""
    try:
        return await service.update(data, user.pk)
    except RecipeDoesNotExistError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from None
    except RecipeAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message) from None


@router.get("/recipes/like/", status_code=status.HTTP_200_OK)
async def get_recipe_like(snippet: str, service: RecipeServiceDep, user: CurrentUser) -> schemas.Recipes:
    """Get a recipe by snippet."""
    return await service.like(snippet, user.pk)


@router.post("/timings", status_code=status.HTTP_201_CREATED)
async def create_timings(
    data: schemas.TimingsCreate, service: TimingsServiceDep, user: CurrentUser
) -> schemas.TimingsResponse:
    """Creates the timings in the given database."""
    try:
        return await service.create(data, user.pk)
    except TimingAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message) from None


@router.get("/timings", status_code=status.HTTP_200_OK)
async def get_timings(service: TimingsServiceDep, user: CurrentUser) -> schemas.TimingsResponse:
    """Get the timings by the primary key of that timing."""
    timings = await service.get(user.pk)

    if timings is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timing does not exist.")

    return timings


@router.patch("/timings", status_code=status.HTTP_200_OK)
async def update_timings(
    timings_data: schemas.TimingsCreate, service: TimingsServiceDep, user: CurrentUser
) -> schemas.TimingsResponse:
    """Get the timings by the primary key of that timing."""
    return await service.update(timings_data, user.pk)


@router.post("/planned_day", status_code=status.HTTP_201_CREATED)
async def update_planned_day(
    data: schemas.PlannedDay, service: PlanServiceDep, user: CurrentUser
) -> schemas.PlannedDayResponse:
    """Update the planned day."""
    try:
        return await service.plan(data, user.pk)
    except RecipeDoesNotExistError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from None


@router.get("/planned_day", status_code=status.HTTP_200_OK)
async def get_plans(
    start_date: date, end_date: date, service: PlanServiceDep, user: CurrentUser
) -> list[schemas.PlannedDayResponse]:
    """Get the plans over the given range."""
    return await service.get_range(start_date, end_date, user.pk)


@router.get("/planned_day/summary/", status_code=status.HTTP_200_OK)
async def plan_summary(service: PlanServiceDep, user: CurrentUser) -> list[schemas.RecipeSummary]:
    """Get the plans over the given range."""
    return await service.summary(user.pk)
