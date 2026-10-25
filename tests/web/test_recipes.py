from typing import TYPE_CHECKING

from inline_snapshot import external
from starlette import status

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestRecipesAPI:
    async def test_get_recipe(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        json_result = response.json()
        pk = json_result["pk"]

        response = await client.get(f"/recipe/{pk}")

        assert response.text == external("uuid:435bfb88-5a75-41c2-84ee-a75e8237f184.txt")

    async def test_get_recipes(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        pk = response.json().get("pk")

        assert pk is not None

        response = await client.get("/recipes")

        assert response.text == external("uuid:c27cf730-5ec8-49ff-a1a0-293cc267fc4f.txt")

    async def test_get_recipe_names(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        pk = response.json().get("pk")

        assert pk is not None

        response = await client.get("/recipe_list")

        assert response.text == external("uuid:ee140c45-c153-492c-9ed1-3d0629cd9ffd.txt")

    async def test_update_recipe(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        json_result = response.json()
        json_result["name"] = "Carrot stew"
        json_result["ingredients"] = ["Carrot 10 units"]
        pk = json_result["pk"]

        response = await client.post(f"/update_recipe/{pk}", data=json_result)

        assert response.text == external("uuid:6020747d-93b4-4204-a629-05d1397c361c.txt")

    async def test_update_recipe_error(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        json_result = response.json()
        json_result["ingredients"] = ["Carrot x units"]
        pk = json_result["pk"]

        response = await client.post(f"/update_recipe/{pk}", data=json_result)

        assert response.text == external("uuid:5082a7a0-a5fb-4135-a0ea-2923a83f682b.txt")

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

        assert response.text == external("uuid:1c790be2-234d-4760-a157-e9f5674bc83e.txt")

    async def test_get_missing_recipe(self, client: AsyncClient):
        response = await client.get("/recipe/9999")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_edit_missing_recipe(self, client: AsyncClient):
        response = await client.get("/recipe/9999/edit")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestNewRecipeAPI:
    async def test_get_new_page(self, client: AsyncClient):
        response = await client.get("/new.html")

        assert response.text == external("uuid:ac29b30e-908a-4923-b547-323a96ac28c4.txt")

    async def test_new_recipe_success(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": ["Flour 2 cups"], "instructions": "Test steps"}
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.text == external("uuid:7cc71c6a-a97a-4da6-badb-33e3f217338b.txt")
        assert response.status_code == status.HTTP_200_OK

        check = await client.get("/api/v1/recipes/", params={"name": "Test"})
        pk = check.json().get("pk")

        assert pk is not None

    async def test_bad_ingredient(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": ["Flour"], "instructions": "Test steps"}
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.text == external("uuid:86353837-4246-4783-bba1-b1f2a9c6d326.txt")

        check = await client.get("/api/v1/recipes/", params={"name": "Test"})
        pk = check.json().get("pk")

        assert pk is None

    async def test_bad_ingredient_quantity(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": ["Flour z cups"], "instructions": "Test steps"}
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.text == external("uuid:32181578-b896-4df8-959e-43e2747c900a.txt")

        check = await client.get("/api/v1/recipes/", params={"name": "Test"})
        pk = check.json().get("pk")

        assert pk is None

    async def test_ingredient_no_unit(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": ["Flour 1"], "instructions": "Test steps"}
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.text == external("uuid:4cb59c1f-bc19-4b10-91c8-b2451f2eac58.txt")

        check = await client.get("/api/v1/recipes/", params={"name": "Test"})
        pk = check.json().get("pk")

        assert pk is None

    async def test_recipe_exists(self, client: AsyncClient):
        new_recipe = {"name": "Test", "ingredients": ["Flour 2 cups"], "instructions": "Test steps"}
        response = await client.post("/new_recipe", data=new_recipe)
        response.raise_for_status()
        response = await client.post("/new_recipe", data=new_recipe)
        response.raise_for_status()

        assert response.text == external("uuid:9d7c702c-8859-4660-812c-7797f6bdc57b.txt")

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
