from datetime import time
from typing import TYPE_CHECKING

from fastapi import status
from inline_snapshot import snapshot as snap

from meals.schemas import CreateIngredientRequest, IngredientResponse, RecipeResponse, Recipes, UpdateRecipeRequest

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestHealthAPI:
    async def test_health(self, client: AsyncClient):
        response = await client.get("/health")

        assert response.status_code == status.HTTP_200_OK


class TestRecipesAPI:
    async def test_create_and_get_recipe(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        pk = response.json().get("pk")

        assert pk is not None

        response = await client.get(f"/api/v1/recipes/{pk}")

        assert response.status_code == status.HTTP_200_OK

        recipe = RecipeResponse.model_validate(response.json())

        assert recipe == snap(
            RecipeResponse(
                pk=1,
                name="Carrot Surprise",
                ingredients=[IngredientResponse(pk=1, name="Carrot", quantity=10.0, unit="units")],
                instructions="Test instructions",
            )
        )

    async def test_create_and_get_recipe_multi_ingredients(self, client: AsyncClient, carrots_recipe):
        carrots_recipe.ingredients.append(CreateIngredientRequest(name="Test", quantity=1, unit="unit"))
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        pk = response.json().get("pk")

        assert pk is not None

        response = await client.get(f"/api/v1/recipes/{pk}")

        assert response.status_code == status.HTTP_200_OK

        recipe = RecipeResponse.model_validate(response.json())

        assert recipe == snap(
            RecipeResponse(
                pk=1,
                name="Carrot Surprise",
                ingredients=[
                    IngredientResponse(pk=1, name="Carrot", quantity=10.0, unit="units"),
                    IngredientResponse(pk=2, name="Test", quantity=1.0, unit="unit"),
                ],
                instructions="Test instructions",
            )
        )

    async def test_create_and_get_recipe_by_name(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        response = await client.get("/api/v1/recipes/", params={"name": carrots_recipe.name})

        assert response.status_code == status.HTTP_200_OK

        recipe = RecipeResponse.model_validate(response.json())

        assert recipe == snap(
            RecipeResponse(
                pk=1,
                name="Carrot Surprise",
                ingredients=[IngredientResponse(pk=1, name="Carrot", quantity=10.0, unit="units")],
                instructions="Test instructions",
            )
        )

    async def test_get_all_recipes(self, client: AsyncClient, carrots_recipe, sweets_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post("/api/v1/recipes", json=sweets_recipe.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

        response = await client.get("/api/v1/recipes")

        assert response.status_code == status.HTTP_200_OK

        recipes = Recipes.model_validate(response.json())

        assert recipes == snap(
            Recipes(
                root=[
                    RecipeResponse(
                        pk=1,
                        name="Carrot Surprise",
                        ingredients=[IngredientResponse(pk=1, name="Carrot", quantity=10.0, unit="units")],
                        instructions="Test instructions",
                    ),
                    RecipeResponse(
                        pk=2,
                        name="Sweets",
                        ingredients=[IngredientResponse(pk=2, name="sweets", quantity=50.0, unit="units")],
                        instructions="More test instructions",
                    ),
                ]
            )
        )

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

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_ingredient_in_common(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        pk = response.json().get("pk")

        assert pk is not None

        new_name = "Carrot 2"
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump() | {"name": new_name})

        assert response.status_code == status.HTTP_201_CREATED

    async def test_create_and_update(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        pk = response.json().get("pk")

        assert pk is not None

        recipe = UpdateRecipeRequest.model_validate(response.json())
        recipe.ingredients[0].quantity = 20

        response = await client.put("/api/v1/recipes", json=recipe.model_dump())

        assert response.json() == snap(
            {
                "pk": 1,
                "name": "Carrot Surprise",
                "ingredients": [{"pk": 1, "name": "Carrot", "quantity": 20.0, "unit": "units"}],
                "instructions": "Test instructions",
            }
        )

    async def test_update_no_create(self, client: AsyncClient, carrots_recipe):
        carrots_json = carrots_recipe.model_dump()
        carrots_json["pk"] = 1
        for i, ing in enumerate(carrots_json["ingredients"], 1):
            ing["pk"] = i
        recipe = RecipeResponse.model_validate(carrots_json)

        response = await client.put("/api/v1/recipes", json=recipe.model_dump())

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_and_update_delete_ingredient(self, client: AsyncClient, carrots_recipe):
        carrots_recipe.ingredients.append(CreateIngredientRequest(name="delete", quantity=1.0, unit="stuff"))
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        assert response.json() == snap(
            {
                "pk": 1,
                "name": "Carrot Surprise",
                "ingredients": [
                    {"pk": 1, "name": "Carrot", "quantity": 10.0, "unit": "units"},
                    {"pk": 2, "name": "delete", "quantity": 1.0, "unit": "stuff"},
                ],
                "instructions": "Test instructions",
            }
        )

        recipe = RecipeResponse.model_validate(response.json())
        del recipe.ingredients[1]

        response = await client.put("/api/v1/recipes", json=recipe.model_dump())

        assert response.json() == snap(
            {
                "pk": 1,
                "name": "Carrot Surprise",
                "ingredients": [{"pk": 1, "name": "Carrot", "quantity": 10.0, "unit": "units"}],
                "instructions": "Test instructions",
            }
        )

    async def test_create_and_update_add_ingredient(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        assert response.json() == snap(
            {
                "pk": 1,
                "name": "Carrot Surprise",
                "ingredients": [
                    {"pk": 1, "name": "Carrot", "quantity": 10.0, "unit": "units"},
                ],
                "instructions": "Test instructions",
            }
        )

        recipe = UpdateRecipeRequest.model_validate(response.json())
        recipe.ingredients.append(CreateIngredientRequest(pk=2, name="new", quantity=1.0, unit="stuff"))

        response = await client.put("/api/v1/recipes", json=recipe.model_dump())

        assert response.json() == snap(
            {
                "pk": 1,
                "name": "Carrot Surprise",
                "ingredients": [
                    {"pk": 1, "name": "Carrot", "quantity": 10.0, "unit": "units"},
                    {"pk": 2, "name": "new", "quantity": 1.0, "unit": "stuff"},
                ],
                "instructions": "Test instructions",
            }
        )

    async def test_create_and_update_add_ingredient_found_on_other_recipe(
        self, client: AsyncClient, carrots_recipe, sweets_recipe
    ):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        _ = await client.post("/api/v1/recipes", json=sweets_recipe.model_dump())

        recipe = RecipeResponse.model_validate(response.json())
        recipe.ingredients.append(sweets_recipe.ingredients[0])

        response = await client.put("/api/v1/recipes", json=recipe.model_dump())

        assert response.json() == snap(
            {
                "pk": 1,
                "name": "Carrot Surprise",
                "ingredients": [
                    {"pk": 1, "name": "Carrot", "quantity": 10.0, "unit": "units"},
                    {"pk": 3, "name": "sweets", "quantity": 50.0, "unit": "units"},
                ],
                "instructions": "Test instructions",
            }
        )


class TestTimingsAPI:
    async def test_create_only_one(self, client: AsyncClient, dummy_timings):
        response = await client.post("/api/v1/timings", json=dummy_timings.model_dump())
        pk = response.json().get("pk")

        assert pk is not None

        response = await client.post("/api/v1/timings", json=dummy_timings.model_dump())
        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_create_then_get(self, client: AsyncClient, dummy_timings):
        timings_json = dummy_timings.model_dump()
        response = await client.post("/api/v1/timings", json=timings_json)
        pk = response.json().get("pk")

        assert pk is not None

        response = await client.get("/api/v1/timings")
        response_json = response.json()
        assert response_json["steps"] == timings_json["steps"]
        assert response_json["finish_time"] == timings_json["finish_time"]

    async def test_get_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/timings")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_then_update(self, client: AsyncClient, dummy_timings):
        timings_json = dummy_timings.model_dump()
        response = await client.post("/api/v1/timings", json=timings_json)
        pk = response.json().get("pk")

        assert pk is not None

        dummy_timings.finish_time = time(12, 0, 0)
        timings_json = dummy_timings.model_dump()
        response = await client.patch("/api/v1/timings", json=timings_json)
        response_json = response.json()
        assert response_json["finish_time"] == "12:00:00"

    async def test_update(self, client: AsyncClient, dummy_timings):
        response = await client.get("/api/v1/timings")

        assert response.status_code == status.HTTP_404_NOT_FOUND

        timings_json = dummy_timings.model_dump()
        response = await client.patch("/api/v1/timings", json=timings_json)
        response_json = response.json()
        assert response_json["steps"] == timings_json["steps"]
        assert response_json["finish_time"] == timings_json["finish_time"]
