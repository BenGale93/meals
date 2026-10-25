from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError
from starlette import status

from meals.schemas import CreateRecipeRequest
from meals.services import RecipeService
from meals.web.core import format_new_recipe_error

from .assertions import assert_page_shell

if TYPE_CHECKING:
    from httpx import AsyncClient


def test_format_new_recipe_error_for_a_named_field():
    with pytest.raises(ValidationError) as exc_info:
        CreateRecipeRequest.model_validate({"name": 1, "ingredients": [], "instructions": ""})

    message = format_new_recipe_error(exc_info.value.errors()[0])

    assert message == "Issue with name: Input should be a valid string"


class TestRecipesAPI:
    async def test_get_recipe(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        json_result = response.json()
        pk = json_result["pk"]

        response = await client.get(f"/recipe/{pk}")

        assert response.status_code == status.HTTP_200_OK
        assert "Carrot Surprise" in response.text
        assert "Carrot 10.0 units" in response.text
        assert "Test instructions" in response.text
        assert f'hx-get="/recipe/{pk}/edit"' in response.text

    async def test_get_recipes(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        pk = response.json().get("pk")

        assert pk is not None

        response = await client.get("/recipes")

        assert response.status_code == status.HTTP_200_OK
        assert "<main" in response.text
        assert "Carrot Surprise" in response.text
        assert "Carrot 10.0 units" in response.text
        assert f'hx-get="/recipe/{pk}/edit"' in response.text

    async def test_get_recipe_names(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        pk = response.json().get("pk")

        assert pk is not None

        response = await client.get("/recipe_list")

        assert response.status_code == status.HTTP_200_OK
        assert "Contents" in response.text
        assert 'href="#Carrot-Surprise"' in response.text
        assert "Carrot Surprise" in response.text

    async def test_update_recipe(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        json_result = response.json()
        json_result["name"] = "Carrot stew"
        json_result["ingredients"] = ["Carrot 10 units"]
        pk = json_result["pk"]

        response = await client.post(f"/update_recipe/{pk}", data=json_result)

        assert response.status_code == status.HTTP_200_OK
        assert "Carrot stew" in response.text
        assert "Carrot Surprise" not in response.text
        assert "Carrot 10.0 units" in response.text
        assert f'hx-get="/recipe/{pk}/edit"' in response.text

    async def test_update_recipe_error(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        json_result = response.json()
        json_result["ingredients"] = ["Carrot x units"]
        pk = json_result["pk"]

        response = await client.post(f"/update_recipe/{pk}", data=json_result)

        assert response.status_code == status.HTTP_200_OK
        assert "Error(s) updating recipe" in response.text
        assert "Issue with ingredient 1" in response.text

    async def test_update_recipe_clears_last_ingredient(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        json_result = response.json()
        pk = json_result["pk"]

        # The edit form submits an empty string for a cleared ingredient.
        json_result["ingredients"] = [""]

        response = await client.post(f"/update_recipe/{pk}", data=json_result)

        assert response.status_code == status.HTTP_200_OK
        assert "validation error" not in response.text.lower()

        check = await client.get(f"/api/v1/recipes/{pk}")
        assert check.json()["ingredients"] == []

    async def test_update_recipe_ignores_blank_ingredient(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": ["Flour 2 cups", "Sugar 1 cups"], "instructions": "Test steps"}
        response = await client.post("/api/v1/recipes", json=new_recipe)
        pk = response.json()["pk"]

        # Blank entries are ignored, so only the sugar is removed.
        response = await client.post(
            f"/update_recipe/{pk}",
            data={"name": "Test", "ingredients": ["Flour 2 cups", ""], "instructions": "Test steps"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "validation error" not in response.text.lower()

        check = await client.get(f"/api/v1/recipes/{pk}")
        assert [i["name"] for i in check.json()["ingredients"]] == ["Flour"]

    async def test_update_recipe_missing_recipe(self, client: AsyncClient):
        response = await client.post(
            "/update_recipe/9999",
            data={"name": "Test", "ingredients": ["Flour 2 cups"], "instructions": "Test steps"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "Recipe does not exist" in response.text

    async def test_edit_recipe(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        json_result = response.json()
        pk = json_result["pk"]

        response = await client.get(f"/recipe/{pk}/edit")

        assert response.status_code == status.HTTP_200_OK
        assert f'hx-post="/update_recipe/{pk}"' in response.text
        assert 'value="Carrot Surprise"' in response.text
        assert 'value="Carrot 10.0 units"' in response.text
        assert "Test instructions" in response.text
        assert f'hx-get="/recipe/{pk}"' in response.text

    async def test_get_missing_recipe(self, client: AsyncClient):
        response = await client.get("/recipe/9999")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_edit_missing_recipe(self, client: AsyncClient):
        response = await client.get("/recipe/9999/edit")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestNewRecipeAPI:
    async def test_get_new_page(self, client: AsyncClient):
        response = await client.get("/new.html")

        assert_page_shell(response)
        assert "Create a New Recipe" in response.text
        assert 'hx-post="/new_recipe"' in response.text
        assert 'placeholder="Flour 2 cups"' in response.text

    async def test_new_recipe_success(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": ["Flour 2 cups"], "instructions": "Test steps"}
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.status_code == status.HTTP_200_OK
        assert 'id="Test"' in response.text
        assert ">Test</h2>" in response.text
        assert "Flour 2.0 cups" in response.text
        assert "Test steps" in response.text

        check = await client.get("/api/v1/recipes/", params={"name": "Test"})
        pk = check.json().get("pk")

        assert pk is not None

    async def test_bad_ingredient(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": ["Flour"], "instructions": "Test steps"}
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.status_code == status.HTTP_200_OK
        assert "Error(s) adding recipe" in response.text
        assert "Issue with ingredient 1" in response.text
        assert "Expected ingredient to be in form" in response.text

        check = await client.get("/api/v1/recipes/", params={"name": "Test"})
        pk = check.json().get("pk")

        assert pk is None

    async def test_bad_ingredient_quantity(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": ["Flour z cups"], "instructions": "Test steps"}
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.status_code == status.HTTP_200_OK
        assert "Error(s) adding recipe" in response.text
        assert "Issue with ingredient 1" in response.text
        assert "Expected ingredient to be in form" in response.text

        check = await client.get("/api/v1/recipes/", params={"name": "Test"})
        pk = check.json().get("pk")

        assert pk is None

    async def test_ingredient_no_unit(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": ["Flour 1"], "instructions": "Test steps"}
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.status_code == status.HTTP_200_OK
        assert "Error(s) adding recipe" in response.text
        assert "Issue with ingredient 1" in response.text
        assert "Expected ingredient to be in form" in response.text

        check = await client.get("/api/v1/recipes/", params={"name": "Test"})
        pk = check.json().get("pk")

        assert pk is None

    async def test_recipe_exists(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": ["Flour 2 cups"], "instructions": "Test steps"}
        response = await client.post("/new_recipe", data=new_recipe)
        response.raise_for_status()
        response = await client.post("/new_recipe", data=new_recipe)
        response.raise_for_status()

        assert response.status_code == status.HTTP_200_OK
        assert "Recipe already exists. Choose a different name." in response.text

    async def test_unexpected_error(self, client: AsyncClient, monkeypatch):
        async def fail(*_args, **_kwargs):
            msg = "boom"
            raise RuntimeError(msg)

        monkeypatch.setattr(RecipeService, "create", fail)

        response = await client.post(
            "/new_recipe",
            data={"name": "Test", "ingredients": ["Flour 2 cups"], "instructions": "Test steps"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "Unexpected error adding a recipe" in response.text

    async def test_new_recipe_no_ingredients_no_instructions(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": [], "instructions": ""}
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.status_code == status.HTTP_200_OK

        check = await client.get("/api/v1/recipes/", params={"name": "Test"})
        pk = check.json().get("pk")
        assert pk is not None

    async def test_new_recipe_blank_ingredients_no_instructions(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": [""], "instructions": ""}
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.status_code == status.HTTP_200_OK

        check = await client.get("/api/v1/recipes/", params={"name": "Test"})
        pk = check.json().get("pk")
        assert pk is not None

    async def test_new_recipe_no_instructions_fails(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": ["Flour 2 cups"], "instructions": ""}
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.status_code == status.HTTP_200_OK

        check = await client.get("/api/v1/recipes/", params={"name": "Test"})
        pk = check.json().get("pk")
        assert pk is None

    async def test_new_recipe_no_ingredients_fails(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": [], "instructions": "Test steps"}
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.status_code == status.HTTP_200_OK

        check = await client.get("/api/v1/recipes/", params={"name": "Test"})
        pk = check.json().get("pk")
        assert pk is None
