import base64
import datetime
from typing import TYPE_CHECKING

from fastapi import status
from inline_snapshot import snapshot as snap

from meals.schemas import (
    CreateIngredientRequest,
    IngredientResponse,
    PlannedDayResponse,
    PlannedRecipe,
    RecipeResponse,
    Recipes,
    RecipeSummary,
    UpdateRecipeRequest,
)

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestHealthAPI:
    async def test_health(self, client: AsyncClient):
        response = await client.get("/health")

        assert response.status_code == status.HTTP_200_OK


class TestUsersAPI:
    async def test_cant_create_same_user(self, client: AsyncClient, user_one):
        response = await client.post("/api/v1/users", json=user_one.model_dump())

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_read_me(self, client: AsyncClient):
        response = await client.get("/api/v1/users/me")

        assert response.status_code == status.HTTP_200_OK

        user = response.json()

        assert user["user_name"] == snap("User One")


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

    async def test_get_all_recipes(self, client: AsyncClient, carrots_recipe, sweets_recipe, take_away):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post("/api/v1/recipes", json=sweets_recipe.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post("/api/v1/recipes", json=take_away.model_dump())

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

    async def test_get_all_recipes_even_without_ingredients(
        self, client: AsyncClient, carrots_recipe, sweets_recipe, take_away
    ):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post("/api/v1/recipes", json=sweets_recipe.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post("/api/v1/recipes", json=take_away.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

        response = await client.get("/api/v1/recipes", params={"has_ingredients": False})

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
                    RecipeResponse(pk=3, name="Take Away", ingredients=[], instructions=""),
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

    async def test_is_like_recipe(self, client: AsyncClient, carrots_recipe, sweets_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post("/api/v1/recipes", json=sweets_recipe.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

        response = await client.get("/api/v1/recipes/like/", params={"snippet": "Car"})

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
                    )
                ]
            )
        )

    async def test_create_fails_if_not_a_user(self, bad_client: AsyncClient, carrots_recipe):
        headers = {"Authorization": "Basic " + base64.b64encode(b"fake:test").decode()}
        response = await bad_client.post("/api/v1/recipes", json=carrots_recipe.model_dump(), headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_fails_if_wrong_user(self, client: AsyncClient, user_two_client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

        pk = response.json().get("pk")

        response = await user_two_client.get(f"/api/v1/recipes/{pk}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


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

        dummy_timings.finish_time = datetime.time(12, 0, 0)
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


class TestPlannedDayAPI:
    async def test_update_recipe(self, client: AsyncClient, take_away, carrots_recipe):
        recipe_response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        _ = await client.post("/api/v1/recipes", json=take_away.model_dump())

        recipe = recipe_response.json()

        response = await client.post(
            "/api/v1/planned_day",
            json={
                "day": "2025-01-01",
                "recipe": {"pk": recipe["pk"], "name": recipe["name"]},
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

        plan = PlannedDayResponse.model_validate(response.json())

        assert plan == snap(
            PlannedDayResponse(pk=1, day=datetime.date(2025, 1, 1), recipe=PlannedRecipe(pk=1, name="Carrot Surprise"))
        )

    async def test_double_update(self, client: AsyncClient, take_away, carrots_recipe):
        recipe_response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        meal_response = await client.post("/api/v1/recipes", json=take_away.model_dump())

        meal = meal_response.json()

        response = await client.post(
            "/api/v1/planned_day",
            json={
                "day": "2025-01-01",
                "recipe": {"pk": meal["pk"], "name": meal["name"]},
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

        plan = PlannedDayResponse.model_validate(response.json())

        assert plan == snap(
            PlannedDayResponse(pk=1, day=datetime.date(2025, 1, 1), recipe=PlannedRecipe(pk=2, name="Take Away"))
        )

        recipe = recipe_response.json()

        response = await client.post(
            "/api/v1/planned_day",
            json={
                "day": "2025-01-01",
                "recipe": {"pk": recipe["pk"], "name": recipe["name"]},
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

        plan = PlannedDayResponse.model_validate(response.json())

        assert plan == snap(
            PlannedDayResponse(pk=1, day=datetime.date(2025, 1, 1), recipe=PlannedRecipe(pk=1, name="Carrot Surprise"))
        )

    async def test_get_range(self, client: AsyncClient, carrots_recipe):
        recipe_response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        recipe = recipe_response.json()

        for day in ["2025-01-01", "2025-02-01", "2025-03-01"]:
            _ = await client.post(
                "/api/v1/planned_day",
                json={
                    "day": day,
                    "meal": {"pk": recipe["pk"], "name": recipe["name"]},
                },
            )

        response = await client.get(
            "/api/v1/planned_day", params={"start_date": "2025-01-01", "end_date": "2025-02-20"}
        )
        assert response.status_code == status.HTTP_200_OK

        plan = [PlannedDayResponse.model_validate(d) for d in response.json()]

        assert plan == snap([])

    async def test_summarise(self, client: AsyncClient, take_away, carrots_recipe):
        recipe_response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        _ = await client.post("/api/v1/recipes", json=take_away.model_dump())

        recipe = recipe_response.json()

        _ = await client.post(
            "/api/v1/planned_day",
            json={
                "day": "2025-01-01",
                "meal": {"pk": recipe["pk"], "name": recipe["name"]},
            },
        )
        _ = await client.post(
            "/api/v1/planned_day",
            json={
                "day": "2025-01-02",
                "meal": {"pk": recipe["pk"], "name": recipe["name"]},
            },
        )

        summary_response = await client.get("/api/v1/planned_day/summary/")

        summary = [RecipeSummary.model_validate(s) for s in summary_response.json()]

        assert summary == snap(
            [
                RecipeSummary(name="Carrot Surprise", count=0, last_eaten=None),
                RecipeSummary(name="Take Away", count=0, last_eaten=None),
            ]
        )
