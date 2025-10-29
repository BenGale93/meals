from typing import TYPE_CHECKING

from inline_snapshot import external

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestViewAPI:
    async def test_get_index(self, client: AsyncClient):
        response = await client.get("/")

        assert response.text == external("uuid:c2fba73d-0743-47cb-93b3-13735fa031f8.txt")


class TestRecipesAPI:
    async def test_get_recipes(self, client: AsyncClient, carrots_recipe):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        pk = response.json().get("pk")

        assert pk is not None

        response = await client.get("/recipes")

        assert response.text == external("uuid:c27cf730-5ec8-49ff-a1a0-293cc267fc4f.txt")
