from typing import TYPE_CHECKING

from inline_snapshot import external
from starlette import status

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestViewAPI:
    async def test_get_index(self, client: AsyncClient):
        response = await client.get("/")

        assert response.text == external("uuid:c2fba73d-0743-47cb-93b3-13735fa031f8.txt")

    async def test_get_new_recipe(self, client: AsyncClient):
        response = await client.get("/new.html")

        assert response.text == external("uuid:efb61175-7f7a-4a21-be06-fada95992420.txt")


class TestRecipesAPI:
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


class TestNewRecipeAPI:
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
        _ = await client.post("/new_recipe", data=new_recipe)
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.text == external("uuid:9d7c702c-8859-4660-812c-7797f6bdc57b.txt")
