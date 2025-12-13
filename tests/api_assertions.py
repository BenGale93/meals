"""Assertion helpers for API tests."""

import typing as t
from functools import partial

from fastapi import status
from pydantic import BaseModel

from meals.schemas import PlannedDayResponse, RecipeResponse, UpdateRecipeRequest

if t.TYPE_CHECKING:
    from httpx import Response


def assert_status_code(response: Response, expected_status: int) -> None:
    """Assert that response has expected status code."""
    assert response.status_code == expected_status, (
        f"Expected status {expected_status}, got {response.status_code}. Response: {response.text}"
    )


def assert_created(response: Response) -> None:
    """Assert that response indicates successful creation."""
    assert_status_code(response, status.HTTP_201_CREATED)


def assert_ok(response: Response) -> None:
    """Assert that response indicates success."""
    assert_status_code(response, status.HTTP_200_OK)


def assert_not_found(response: Response) -> None:
    """Assert that response indicates not found."""
    assert_status_code(response, status.HTTP_404_NOT_FOUND)


def assert_conflict(response: Response) -> None:
    """Assert that response indicates conflict."""
    assert_status_code(response, status.HTTP_409_CONFLICT)


def assert_unauthorized(response: Response) -> None:
    """Assert that response indicates unauthorized."""
    assert_status_code(response, status.HTTP_401_UNAUTHORIZED)


def assert_has_pk(response: Response) -> int:
    """Assert response has a pk field and return it."""
    pk = response.json().get("pk")
    assert pk is not None, "Response should have a 'pk' field"
    assert isinstance(pk, int)
    return pk


def assert_ok_and_convert[T: BaseModel](response: Response, model: type[T]) -> T:
    assert_ok(response)
    return model.model_validate(response.json())


async def assert_created_pk(client, data: dict[str, t.Any] | BaseModel, url: str) -> int:
    """Assert that a model can be created and return its pk."""
    json_data = data.model_dump() if isinstance(data, BaseModel) else data
    response = await client.post(f"/api/v1/{url}", json=json_data)
    assert_created(response)
    return assert_has_pk(response)


async def assert_planned_day(client, data: dict[str, t.Any], day: str = "2025-01-01") -> PlannedDayResponse:
    response = await client.post(
        "/api/v1/planned_day",
        json={
            "day": day,
            "recipe": {"pk": data["pk"], "name": data["name"]},
        },
    )

    assert_created(response)

    return PlannedDayResponse.model_validate(response.json())


async def _assert_get_recipe[T: BaseModel](client, pk: int, base_model: type[T]) -> T:
    response = await client.get(f"/api/v1/recipes/{pk}")
    return assert_ok_and_convert(response, base_model)


assert_get_recipe_for_update = partial(_assert_get_recipe, base_model=UpdateRecipeRequest)

assert_get_recipe = partial(_assert_get_recipe, base_model=RecipeResponse)


async def assert_update_recipe(client, recipe: UpdateRecipeRequest) -> RecipeResponse:
    response = await client.put("/api/v1/recipes", json=recipe.model_dump())
    return assert_ok_and_convert(response, RecipeResponse)
