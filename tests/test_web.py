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

    async def test_edit_recipe(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        json_result = response.json()
        pk = json_result["pk"]

        response = await client.get(f"/recipe/{pk}/edit")

        assert response.text == external("uuid:1c790be2-234d-4760-a157-e9f5674bc83e.txt")


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
        _ = await client.post("/new_recipe", data=new_recipe)
        response = await client.post("/new_recipe", data=new_recipe)

        assert response.text == external("uuid:9d7c702c-8859-4660-812c-7797f6bdc57b.txt")


class TestTimingsAPI:
    async def test_get_index(self, client: AsyncClient):
        response = await client.get("/timings.html")

        assert response.text == external("uuid:4f1d948c-f93c-45aa-8a23-9f6313ce0029.txt")

    async def test_get_placeholder_timings(self, client: AsyncClient):
        response = await client.get("/timings")
        assert response.text == external("uuid:c7fc40cc-df47-4d31-b9d6-8e854e9042f3.txt")
        assert response.status_code == status.HTTP_200_OK

    async def test_get_existing_timings(self, client: AsyncClient):
        new_timings = {"finish_time": "12:00:00", "steps": '[{"description": "End", "offset": 0}]'}
        response = await client.patch("/timings", data=new_timings)

        response = await client.get("/timings")
        assert response.text == external("uuid:d2116b7b-a0d7-4b66-8e69-b8a6e91a77d1.txt")
        assert response.status_code == status.HTTP_200_OK
        assert "12:00:00" in response.text

    async def test_update_timings(self, client: AsyncClient):
        new_timings = {"finish_time": "12:00:00", "steps": '[{"description": "End", "offset": 0}]'}
        response = await client.patch("/timings", data=new_timings)

        assert response.text == external("uuid:2646a836-6c9e-4f73-a93c-b47f075457f0.txt")
        assert response.status_code == status.HTTP_200_OK

        check = await client.get("/api/v1/timings")
        pk = check.json().get("pk")

        assert pk is not None

    async def test_update_timings_failure(self, client: AsyncClient):
        new_timings = {"finish_time": "12:00:00", "steps": '[{"description": "End", "offset": 10}]'}
        response = await client.patch("/timings", data=new_timings)

        assert response.text == external("uuid:f577cc02-d394-4019-b6fa-50584bbebff0.txt")
        assert "Error" in response.text
