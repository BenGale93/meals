import base64
from functools import partial
from typing import TYPE_CHECKING

from fastapi import status
from inline_snapshot import snapshot as snap

from meals.constants import LABEL_LENGTH
from meals.schemas import (
    CreateIngredientRequest,
    CreateLabel,
    CreateRecipeRequest,
    IngredientResponse,
    RecipeLabelResponse,
    RecipeResponse,
    Recipes,
    UpdateRecipeRequest,
)
from tests import api_assertions

if TYPE_CHECKING:
    from httpx import AsyncClient

assert_created_pk = partial(api_assertions.assert_created_pk, url="recipes")


class TestRecipesAPI:
    async def test_create_and_get_recipe(self, client: AsyncClient, carrots_recipe):
        pk = await assert_created_pk(client, carrots_recipe)

        response = await client.get(f"/api/v1/recipes/{pk}")
        recipe = api_assertions.assert_ok_and_convert(response, RecipeResponse)

        assert recipe == snap(
            RecipeResponse(
                pk=1,
                name="Carrot Surprise",
                ingredients=[IngredientResponse(pk=1, name="Carrot", quantity=10.0, unit="units")],
                instructions="Test instructions",
            )
        )

    async def test_create_and_get_recipe_by_name(self, client: AsyncClient, carrots_recipe):
        await assert_created_pk(client, carrots_recipe)

        response = await client.get("/api/v1/recipes/", params={"name": carrots_recipe.name})
        recipe = api_assertions.assert_ok_and_convert(response, RecipeResponse)

        assert recipe == snap(
            RecipeResponse(
                pk=1,
                name="Carrot Surprise",
                ingredients=[IngredientResponse(pk=1, name="Carrot", quantity=10.0, unit="units")],
                instructions="Test instructions",
            )
        )

    async def test_get_all_recipes(self, client: AsyncClient, carrots_recipe, sweets_recipe, take_away):
        for recipe in [carrots_recipe, sweets_recipe, take_away]:
            await assert_created_pk(client, recipe)

        response = await client.get("/api/v1/recipes")
        recipes = api_assertions.assert_ok_and_convert(response, Recipes)

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
        for recipe in [carrots_recipe, sweets_recipe, take_away]:
            await assert_created_pk(client, recipe)

        response = await client.get("/api/v1/recipes", params={"has_ingredients": False})
        recipes = api_assertions.assert_ok_and_convert(response, Recipes)

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

        api_assertions.assert_not_found(response)

    async def test_recipe_name_not_found(self, client: AsyncClient, carrots_recipe):
        await assert_created_pk(client, carrots_recipe)

        response = await client.get("/api/v1/recipes/", params={"name": "sweets"})

        api_assertions.assert_not_found(response)

    async def test_create_does_not_override(self, client: AsyncClient, carrots_recipe):
        await assert_created_pk(client, carrots_recipe)

        new_instructions = "New instructions"

        response = await client.post(
            "/api/v1/recipes", json=carrots_recipe.model_dump() | {"instructions": new_instructions}
        )

        api_assertions.assert_conflict(response)

    async def test_update_no_create(self, client: AsyncClient, carrots_recipe):
        carrots_json = carrots_recipe.model_dump()
        carrots_json["pk"] = 1
        for i, ing in enumerate(carrots_json["ingredients"], 1):
            ing["pk"] = i
        recipe = UpdateRecipeRequest.model_validate(carrots_json)

        response = await client.put("/api/v1/recipes", json=recipe.model_dump())

        api_assertions.assert_not_found(response)

    async def test_is_like_recipe(self, client: AsyncClient, carrots_recipe, sweets_recipe):
        for recipe in [carrots_recipe, sweets_recipe]:
            await assert_created_pk(client, recipe)

        response = await client.get("/api/v1/recipes/like/", params={"snippet": "Car"})

        recipes = api_assertions.assert_ok_and_convert(response, Recipes)

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


class TestRecipesAuthAPI:
    async def test_create_fails_if_not_a_user(self, bad_client: AsyncClient, carrots_recipe):
        headers = {"Authorization": "Basic " + base64.b64encode(b"fake:test").decode()}
        response = await bad_client.post("/api/v1/recipes", json=carrots_recipe.model_dump(), headers=headers)

        api_assertions.assert_unauthorized(response)

    async def test_get_fails_if_wrong_user(self, client: AsyncClient, user_two_client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        api_assertions.assert_created(response)

        pk = response.json().get("pk")

        response = await user_two_client.get(f"/api/v1/recipes/{pk}")

        api_assertions.assert_not_found(response)


class TestRecipesIngredientsAPI:
    async def test_create_and_get_recipe_multi_ingredients(self, client: AsyncClient, carrots_recipe):
        carrots_recipe.ingredients.append(CreateIngredientRequest(name="Test", quantity=1, unit="unit"))
        pk = await assert_created_pk(client, carrots_recipe)

        response = await client.get(f"/api/v1/recipes/{pk}")
        recipe = api_assertions.assert_ok_and_convert(response, RecipeResponse)

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

    async def test_ingredient_in_common(self, client: AsyncClient, carrots_recipe):
        await assert_created_pk(client, carrots_recipe)

        new_name = "Carrot 2"
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump() | {"name": new_name})

        api_assertions.assert_created(response)

    async def test_create_and_update(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        api_assertions.assert_created(response)

        recipe = UpdateRecipeRequest.model_validate(response.json())
        recipe.ingredients[0].quantity = 20

        response = await client.put("/api/v1/recipes", json=recipe.model_dump())

        assert response.json() == snap(
            {
                "pk": 1,
                "name": "Carrot Surprise",
                "ingredients": [{"pk": 1, "name": "Carrot", "quantity": 20.0, "unit": "units"}],
                "instructions": "Test instructions",
                "labels": [],
            }
        )

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
                "labels": [],
            }
        )

        recipe = UpdateRecipeRequest.model_validate(response.json())
        del recipe.ingredients[1]

        response = await client.put("/api/v1/recipes", json=recipe.model_dump())

        assert response.json() == snap(
            {
                "pk": 1,
                "name": "Carrot Surprise",
                "ingredients": [{"pk": 1, "name": "Carrot", "quantity": 10.0, "unit": "units"}],
                "instructions": "Test instructions",
                "labels": [],
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
                "labels": [],
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
                "labels": [],
            }
        )

    async def test_create_and_update_add_ingredient_found_on_other_recipe(
        self, client: AsyncClient, carrots_recipe, sweets_recipe
    ):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        response.raise_for_status()
        response_2 = await client.post("/api/v1/recipes", json=sweets_recipe.model_dump())
        response_2.raise_for_status()

        recipe = UpdateRecipeRequest.model_validate(response.json())
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
                "labels": [],
            }
        )


class TestRecipesLabelsAPI:
    async def test_create_with_labels(self, client: AsyncClient, sausage_recipe):
        pk = await assert_created_pk(client, sausage_recipe)
        recipe = await api_assertions.assert_get_recipe_for_update(client, pk)

        assert recipe.labels == snap([CreateLabel(category="meat", sub_category="pork")])

    async def test_create_update_remove_label(self, client: AsyncClient, sausage_recipe):
        pk = await assert_created_pk(client, sausage_recipe)
        recipe = await api_assertions.assert_get_recipe_for_update(client, pk)

        assert recipe.labels == snap([CreateLabel(category="meat", sub_category="pork")])

        del recipe.labels[0]

        recipe_updated = await api_assertions.assert_update_recipe(client, recipe)

        assert recipe_updated.labels == snap([])

    async def test_create_update_add_label(self, client: AsyncClient, sausage_recipe):
        pk = await assert_created_pk(client, sausage_recipe)
        recipe = await api_assertions.assert_get_recipe_for_update(client, pk)

        assert recipe.labels == snap([CreateLabel(category="meat", sub_category="pork")])

        recipe.labels.append(CreateLabel(category="carb", sub_category="chips"))

        assert len(recipe.labels) == 2

        recipe_updated = await api_assertions.assert_update_recipe(client, recipe)

        assert recipe_updated.labels == snap(
            [
                RecipeLabelResponse(pk=1, category="meat", sub_category="pork"),
                RecipeLabelResponse(pk=2, category="carb", sub_category="chips"),
            ]
        )

    async def test_update_with_label_already_in_db(self, client: AsyncClient, sausage_recipe):
        recipe_json = sausage_recipe.model_dump()
        await assert_created_pk(client, recipe_json)

        recipe_json["name"] = "Other name"

        pk = await assert_created_pk(client, recipe_json)

        recipe = await api_assertions.assert_get_recipe(client, pk)

        assert recipe.labels == snap([RecipeLabelResponse(pk=2, category="meat", sub_category="pork")])

    async def test_update_label_sub_category(self, client: AsyncClient, sausage_recipe):
        recipe_json = sausage_recipe.model_dump()
        await assert_created_pk(client, recipe_json)

        recipe_json["name"] = "Other name"
        recipe_json["labels"] = [{"category": "meat", "sub_category": "sausage"}]

        pk = await assert_created_pk(client, recipe_json)

        recipe = await api_assertions.assert_get_recipe(client, pk)

        assert recipe.labels == snap([RecipeLabelResponse(pk=2, category="meat", sub_category="sausage")])

    async def test_update_label_category(self, client: AsyncClient, sausage_recipe):
        recipe_json = sausage_recipe.model_dump()
        await assert_created_pk(client, recipe_json)

        recipe_json["name"] = "Other name"
        recipe_json["labels"] = [{"category": "protein", "sub_category": "pork"}]

        pk = await assert_created_pk(client, recipe_json)

        recipe = await api_assertions.assert_get_recipe(client, pk)

        assert recipe.labels == snap([RecipeLabelResponse(pk=2, category="protein", sub_category="pork")])

    async def test_label_length_validation_max(self, client):
        recipe_data = CreateRecipeRequest.model_validate(
            {
                "name": "Test Recipe",
                "instructions": "",
                "ingredients": [],
                "labels": [{"category": "a" * LABEL_LENGTH, "sub_category": "a" * LABEL_LENGTH}],
            }
        )

        await assert_created_pk(client, recipe_data)

    async def test_label_length_validation_too_long(self, client):
        recipe_data = {
            "name": "Test Recipe",
            "instructions": "",
            "ingredients": [],
            "labels": [{"category": "a" * (LABEL_LENGTH + 1), "sub_category": "test"}],
        }

        response = await client.post("/api/v1/recipes", json=recipe_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_empty_label_category(self, client):
        recipe_data = {
            "name": "Test Recipe",
            "instructions": "",
            "ingredients": [],
            "labels": [{"category": "", "sub_category": "test"}],
        }

        response = await client.post("/api/v1/recipes", json=recipe_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_empty_label_sub_category(self, client):
        recipe_data = {
            "name": "Test Recipe",
            "instructions": "",
            "ingredients": [],
            "labels": [{"category": "test", "sub_category": ""}],
        }

        response = await client.post("/api/v1/recipes", json=recipe_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_duplicate_label_on_same_recipe(self, client):
        recipe_data = {
            "name": "Test Recipe",
            "instructions": "",
            "ingredients": [],
            "labels": [
                {"category": "meat", "sub_category": "beef"},
                {"category": "meat", "sub_category": "beef"},
            ],
        }

        response = await client.post("/api/v1/recipes", json=recipe_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_same_label_on_different_recipes(self, client):
        label = {"category": "meat", "sub_category": "beef"}

        recipe1 = CreateRecipeRequest.model_validate(
            {"name": "Beef Stew", "instructions": "", "ingredients": [], "labels": [label]}
        )

        response1 = await client.post("/api/v1/recipes", json=recipe1.model_dump())
        api_assertions.assert_created(response1)

        recipe2 = CreateRecipeRequest.model_validate(
            {"name": "Beef Burgers", "instructions": "", "ingredients": [], "labels": [label]}
        )

        response2 = await client.post("/api/v1/recipes", json=recipe2.model_dump())
        api_assertions.assert_created(response2)

        recipe1_response = await client.get(f"/api/v1/recipes/{response1.json()['pk']}")
        recipe2_response = await client.get(f"/api/v1/recipes/{response2.json()['pk']}")

        api_assertions.assert_ok(recipe1_response)
        api_assertions.assert_ok(recipe2_response)

        assert len(recipe1_response.json()["labels"]) == 1
        assert len(recipe2_response.json()["labels"]) == 1

    async def test_case_sensitive_labels(self, client):
        recipe1 = CreateRecipeRequest.model_validate(
            {
                "name": "Test Recipe 1",
                "instructions": "",
                "ingredients": [],
                "labels": [{"category": "meat", "sub_category": "beef"}],
            }
        )

        response1 = await client.post("/api/v1/recipes", json=recipe1.model_dump())
        api_assertions.assert_created(response1)

        recipe2 = CreateRecipeRequest.model_validate(
            {
                "name": "Test Recipe 2",
                "instructions": "",
                "ingredients": [],
                "labels": [{"category": "Meat", "sub_category": "Beef"}],
            }
        )

        response2 = await client.post("/api/v1/recipes", json=recipe2.model_dump())
        api_assertions.assert_created(response2)

        recipe1_data = await api_assertions.assert_get_recipe(client, response1.json()["pk"])
        recipe2_data = await api_assertions.assert_get_recipe(client, response2.json()["pk"])

        assert recipe1_data.labels[0].category == "meat"
        assert recipe1_data.labels[0].sub_category == "beef"
        assert recipe2_data.labels[0].category == "Meat"
        assert recipe2_data.labels[0].sub_category == "Beef"

    async def test_special_characters_in_labels(self, client):
        recipe_data = CreateRecipeRequest.model_validate(
            {
                "name": "Test Recipe",
                "instructions": "",
                "ingredients": [],
                "labels": [{"category": "test-123", "sub_category": "special!@#"}],
            }
        )

        response = await client.post("/api/v1/recipes", json=recipe_data.model_dump())
        api_assertions.assert_created(response)

    async def test_multiple_labels_same_category(self, client):
        recipe_data = CreateRecipeRequest.model_validate(
            {
                "name": "Test Recipe",
                "instructions": "",
                "ingredients": [],
                "labels": [
                    {"category": "meat", "sub_category": "beef"},
                    {"category": "meat", "sub_category": "pork"},
                    {"category": "meat", "sub_category": "chicken"},
                ],
            }
        )

        response = await client.post("/api/v1/recipes", json=recipe_data.model_dump())
        api_assertions.assert_created(response)

        recipe = await api_assertions.assert_get_recipe(client, response.json()["pk"])
        assert len(recipe.labels) == 3

    async def test_multiple_labels_different_categories_same_subcategory(self, client):
        recipe_data = CreateRecipeRequest.model_validate(
            {
                "name": "Test Recipe",
                "instructions": "",
                "ingredients": [],
                "labels": [
                    {"category": "meat", "sub_category": "beef"},
                    {"category": "vegetable", "sub_category": "beef"},
                ],
            }
        )

        response = await client.post("/api/v1/recipes", json=recipe_data.model_dump())
        api_assertions.assert_created(response)

        recipe = await api_assertions.assert_get_recipe(client, response.json()["pk"])
        assert len(recipe.labels) == 2

    async def test_remove_all_labels_from_recipe(self, client):
        recipe_data = CreateRecipeRequest.model_validate(
            {
                "name": "Test Recipe",
                "instructions": "",
                "ingredients": [],
                "labels": [
                    {"category": "meat", "sub_category": "beef"},
                    {"category": "carb", "sub_category": "potato"},
                ],
            }
        )

        response = await client.post("/api/v1/recipes", json=recipe_data.model_dump())
        api_assertions.assert_created(response)

        recipe = await api_assertions.assert_get_recipe_for_update(client, response.json()["pk"])
        assert len(recipe.labels) == 2

        recipe.labels = []

        updated_recipe = await api_assertions.assert_update_recipe(client, recipe)
        assert len(updated_recipe.labels) == 0

    async def test_whitespace_in_labels(self, client):
        recipe_data = CreateRecipeRequest.model_validate(
            {
                "name": "Test Recipe",
                "instructions": "",
                "ingredients": [],
                "labels": [{"category": "  meat  ", "sub_category": "  beef  "}],
            }
        )

        response = await client.post("/api/v1/recipes", json=recipe_data.model_dump())
        api_assertions.assert_created(response)

        recipe = await api_assertions.assert_get_recipe(client, response.json()["pk"])
        assert recipe.labels[0].category == "  meat  "
        assert recipe.labels[0].sub_category == "  beef  "

    async def test_with_single_label(self, client, sausage_recipe, burger_recipe):
        await assert_created_pk(client, sausage_recipe)
        await assert_created_pk(client, burger_recipe)

        response = await client.get("/api/v1/recipes")
        recipes = api_assertions.assert_ok_and_convert(response, Recipes)

        assert len(recipes) == 2

        response = await client.post(
            "/api/v1/recipes/with_labels/", json=[{"category": "meat", "sub_category": "pork"}]
        )
        recipes = api_assertions.assert_ok_and_convert(response, Recipes)

        assert len(recipes) == 1

    async def test_with_two_labels(self, client, sausage_recipe, burger_recipe):
        chips_label = CreateLabel(category="carbs", sub_category="chips")
        sausage_recipe.labels.append(chips_label)
        await assert_created_pk(client, sausage_recipe)
        await assert_created_pk(client, burger_recipe)

        response = await client.get("/api/v1/recipes")
        recipes = api_assertions.assert_ok_and_convert(response, Recipes)

        assert len(recipes) == 2

        response = await client.post(
            "/api/v1/recipes/with_labels/",
            json=[{"category": "meat", "sub_category": "pork"}, chips_label.model_dump()],
        )
        recipes = api_assertions.assert_ok_and_convert(response, Recipes)

        assert len(recipes) == 1

    async def test_no_labels_in_search_means_no_recipes(self, client, sausage_recipe, burger_recipe):
        await assert_created_pk(client, sausage_recipe)
        await assert_created_pk(client, burger_recipe)

        response = await client.get("/api/v1/recipes")
        recipes = api_assertions.assert_ok_and_convert(response, Recipes)

        assert len(recipes) == 2

        response = await client.post("/api/v1/recipes/with_labels/")
        recipes = api_assertions.assert_ok_and_convert(response, Recipes)

        assert len(recipes) == 0
