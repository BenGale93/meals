import pytest
from fastapi import status
from httpx import AsyncClient

from meals.schemas import CreateRecipeRequest, RecipeResponse, Recipes


@pytest.fixture
def carrots_recipe():
    return CreateRecipeRequest.model_validate(
        {
            "name": "Carrots",
            "instructions": "Test instructions",
            "ingredients": [{"name": "Carrot", "quantity": 10.0, "unit": "units"}],
        }
    )


@pytest.fixture
def sweets_recipe():
    return CreateRecipeRequest.model_validate(
        {
            "name": "Sweets",
            "instructions": "More test instructions",
            "ingredients": [{"name": "sweets", "quantity": 50.0, "unit": "units"}],
        }
    )


class TestRecipesAPI:
    async def test_create_and_get_recipe(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        pk = response.json().get("pk")

        assert pk is not None

        response = await client.get(f"/api/v1/recipes/{pk}")

        assert response.status_code == status.HTTP_200_OK

        recipe = RecipeResponse.model_validate(response.json())

        assert recipe.pk == pk
        assert recipe.name == "Carrots"

    async def test_create_and_get_recipe_by_name(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        response = await client.get("/api/v1/recipes/", params={"name": "Carrots"})

        assert response.status_code == status.HTTP_200_OK

        recipe = RecipeResponse.model_validate(response.json())

        assert recipe.name == "Carrots"

    async def test_get_all_recipes(self, client: AsyncClient, carrots_recipe, sweets_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post("/api/v1/recipes", json=sweets_recipe.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

        response = await client.get("/api/v1/recipes")

        assert response.status_code == status.HTTP_200_OK

        recipes = Recipes.model_validate(response.json())

        assert len(recipes) == 2

    async def test_recipe_pk_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/recipes/1000")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_recipe_name_not_found(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

        response = await client.get("/api/v1/recipes/", params={"name": "sweets"})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_does_not_override(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        pk = response.json().get("pk")

        assert pk is not None

        new_instructions = "New instructions"

        response = await client.post(
            "/api/v1/recipes", json=carrots_recipe.model_dump() | {"instructions": new_instructions}
        )

        recipe = RecipeResponse.model_validate(response.json())

        assert recipe.instructions != new_instructions

    async def test_ingredient_in_common(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        pk = response.json().get("pk")

        assert pk is not None

        new_name = "Carrot 2"
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump() | {"name": new_name})

        assert response.status_code == status.HTTP_201_CREATED


class TestHealthAPI:
    async def test_health(self, client: AsyncClient):
        response = await client.get("/health")

        assert response.status_code == status.HTTP_200_OK
