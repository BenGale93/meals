import datetime as dt
from typing import TYPE_CHECKING

from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient


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

        dummy_timings.finish_time = dt.time(12, 0, 0)
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
