from typing import TYPE_CHECKING

from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestHealthAPI:
    async def test_health(self, client: AsyncClient):
        response = await client.get("/health")

        assert response.status_code == status.HTTP_200_OK
