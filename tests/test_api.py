import datetime
from functools import partial
from typing import TYPE_CHECKING

import time_machine
from inline_snapshot import snapshot as snap

from meals.schemas import (
    PlannedDay,
    PlannedDayResponse,
    PlannedRecipe,
    RecipeSummary,
)
from tests import api_assertions

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestHealthAPI:
    async def test_health(self, client: AsyncClient):
        response = await client.get("/health")

        api_assertions.assert_ok(response)


class TestUsersAPI:
    async def test_cant_create_same_user(self, client: AsyncClient, user_one):
        response = await client.post("/api/v1/users", json=user_one.model_dump())

        api_assertions.assert_conflict(response)

    async def test_read_me(self, client: AsyncClient):
        response = await client.get("/api/v1/users/me")

        api_assertions.assert_ok(response)

        user = response.json()

        assert user["user_name"] == snap("User One")


assert_created_timings = partial(api_assertions.assert_created_pk, url="timings")


class TestTimingsAPI:
    async def test_create_only_one(self, client: AsyncClient, dummy_timings):
        _ = await assert_created_timings(client, dummy_timings)

        response = await client.post("/api/v1/timings", json=dummy_timings.model_dump())
        api_assertions.assert_conflict(response)

    async def test_create_then_get(self, client: AsyncClient, dummy_timings):
        timings_json = dummy_timings.model_dump()
        _ = await assert_created_timings(client, timings_json)

        response = await client.get("/api/v1/timings")
        api_assertions.assert_ok(response)
        response_json = response.json()
        assert response_json["steps"] == timings_json["steps"]
        assert response_json["finish_time"] == timings_json["finish_time"]

    async def test_get_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/timings")

        api_assertions.assert_not_found(response)

    async def test_create_then_update(self, client: AsyncClient, dummy_timings):
        _ = await assert_created_timings(client, dummy_timings)

        dummy_timings.finish_time = datetime.time(12, 0, 0)
        timings_json = dummy_timings.model_dump()
        response = await client.patch("/api/v1/timings", json=timings_json)
        api_assertions.assert_ok(response)
        response_json = response.json()
        assert response_json["finish_time"] == "12:00:00"

    async def test_update(self, client: AsyncClient, dummy_timings):
        response = await client.get("/api/v1/timings")

        api_assertions.assert_not_found(response)

        timings_json = dummy_timings.model_dump()
        response = await client.patch("/api/v1/timings", json=timings_json)
        api_assertions.assert_ok(response)
        response_json = response.json()
        assert response_json["steps"] == timings_json["steps"]
        assert response_json["finish_time"] == timings_json["finish_time"]


class TestPlannedDayAPI:
    async def test_update_recipe(self, client: AsyncClient, take_away, carrots_recipe):
        await api_assertions.assert_created_pk(client, take_away, url="recipes")
        recipe_response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        recipe = recipe_response.json()

        plan = await api_assertions.assert_planned_day(client, recipe)

        assert plan == snap(
            PlannedDayResponse(pk=1, day=datetime.date(2025, 1, 1), recipe=PlannedRecipe(pk=2, name="Carrot Surprise"))
        )

    async def test_double_update(self, client: AsyncClient, take_away, carrots_recipe):
        recipe_response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        meal_response = await client.post("/api/v1/recipes", json=take_away.model_dump())

        meal = meal_response.json()

        plan = await api_assertions.assert_planned_day(client, meal)

        assert plan == snap(
            PlannedDayResponse(pk=1, day=datetime.date(2025, 1, 1), recipe=PlannedRecipe(pk=2, name="Take Away"))
        )

        recipe = recipe_response.json()

        plan = await api_assertions.assert_planned_day(client, recipe)

        assert plan == snap(
            PlannedDayResponse(pk=1, day=datetime.date(2025, 1, 1), recipe=PlannedRecipe(pk=1, name="Carrot Surprise"))
        )

    async def test_get_range(self, client: AsyncClient, carrots_recipe):
        recipe_response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        recipe = PlannedRecipe.model_validate(recipe_response.json())

        for day in ["2025-01-01", "2025-02-01", "2025-03-01"]:
            planned_day = PlannedDay(day=datetime.date.fromisoformat(day), recipe=recipe)
            response = await client.post("/api/v1/planned_day", json=planned_day.model_dump())
            response.raise_for_status()

        response = await client.get(
            "/api/v1/planned_day", params={"start_date": "2025-01-01", "end_date": "2025-02-20"}
        )
        api_assertions.assert_ok(response)

        plan = [PlannedDayResponse.model_validate(d) for d in response.json()]

        assert plan == snap(
            [
                PlannedDayResponse(
                    pk=1, day=datetime.date(2025, 1, 1), recipe=PlannedRecipe(pk=1, name="Carrot Surprise")
                ),
                PlannedDayResponse(
                    pk=2, day=datetime.date(2025, 2, 1), recipe=PlannedRecipe(pk=1, name="Carrot Surprise")
                ),
            ]
        )

    @time_machine.travel(datetime.date(2025, 1, 1))
    async def test_summarise(self, client: AsyncClient, take_away, carrots_recipe):
        recipe_response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        response = await client.post("/api/v1/recipes", json=take_away.model_dump())
        response.raise_for_status()

        recipe = PlannedRecipe.model_validate(recipe_response.json())
        planned_day = PlannedDay(day=datetime.date(2025, 1, 1), recipe=recipe)

        response = await client.post("/api/v1/planned_day", json=planned_day.model_dump())
        response.raise_for_status()

        planned_day = PlannedDay(day=datetime.date(2025, 1, 2), recipe=recipe)
        response = await client.post("/api/v1/planned_day", json=planned_day.model_dump())
        response.raise_for_status()

        summary_response = await client.get("/api/v1/planned_day/summary/")

        summary = [RecipeSummary.model_validate(s) for s in summary_response.json()]

        assert summary == snap(
            [
                RecipeSummary(name="Carrot Surprise", count=2, last_eaten=datetime.date(2025, 1, 2)),
                RecipeSummary(name="Take Away", count=0, last_eaten=None),
            ]
        )
