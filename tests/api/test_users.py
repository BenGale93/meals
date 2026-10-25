from typing import TYPE_CHECKING

from fastapi import status
from inline_snapshot import snapshot as snap

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestUsersAPI:
    async def test_cant_create_same_user(self, client: AsyncClient, user_one):
        response = await client.post("/api/v1/users", json=user_one.model_dump())

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_read_me(self, client: AsyncClient):
        response = await client.get("/api/v1/users/me")

        assert response.status_code == status.HTTP_200_OK

        user = response.json()

        assert user["user_name"] == snap("User One")
