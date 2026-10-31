from typing import TYPE_CHECKING

from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestLabelsAPI:
    async def test_get_labels_is_sorted(self, client: AsyncClient, burger_recipe, sausage_recipe):
        for recipe in (sausage_recipe, burger_recipe):
            response = await client.post("/api/v1/recipes", json=recipe.model_dump())
            response.raise_for_status()

        response = await client.get("/api/v1/labels")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {"category": "meat", "sub_category": "beef"},
            {"category": "meat", "sub_category": "pork"},
            {"category": "time", "sub_category": "quick"},
            {"category": "time", "sub_category": "slow"},
        ]

    async def test_empty_taxonomy_is_empty(self, client: AsyncClient):
        response = await client.get("/api/v1/labels")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    async def test_get_labels_requires_auth(self, bad_client: AsyncClient):
        response = await bad_client.get("/api/v1/labels")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
