import datetime as dt
from typing import TYPE_CHECKING

import time_machine
from fastapi import status
from inline_snapshot import snapshot as snap

from meals.database.models import StoredPlannedDay
from meals.schemas import PlannedDay, PlannedDayResponse, PlannedRecipe, RecipeSummary

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestPlannedDayAPI:
    async def test_update_recipe(self, client: AsyncClient, take_away, carrots_recipe):
        recipe_response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        response = await client.post("/api/v1/recipes", json=take_away.model_dump())
        response.raise_for_status()

        recipe = recipe_response.json()

        response = await client.post(
            "/api/v1/planned_day",
            json={
                "day": "2025-01-01",
                "recipe": {"pk": recipe["pk"], "name": recipe["name"]},
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

        plan = PlannedDayResponse.model_validate(response.json())

        assert plan == snap(
            PlannedDayResponse(pk=1, day=dt.date(2025, 1, 1), recipe=PlannedRecipe(pk=1, name="Carrot Surprise"))
        )

    async def test_double_update(self, client: AsyncClient, take_away, carrots_recipe):
        recipe_response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        meal_response = await client.post("/api/v1/recipes", json=take_away.model_dump())

        meal = meal_response.json()

        response = await client.post(
            "/api/v1/planned_day",
            json={
                "day": "2025-01-01",
                "recipe": {"pk": meal["pk"], "name": meal["name"]},
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

        plan = PlannedDayResponse.model_validate(response.json())

        assert plan == snap(
            PlannedDayResponse(pk=1, day=dt.date(2025, 1, 1), recipe=PlannedRecipe(pk=2, name="Take Away"))
        )

        recipe = recipe_response.json()

        response = await client.post(
            "/api/v1/planned_day",
            json={
                "day": "2025-01-01",
                "recipe": {"pk": recipe["pk"], "name": recipe["name"]},
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

        plan = PlannedDayResponse.model_validate(response.json())

        assert plan == snap(
            PlannedDayResponse(pk=1, day=dt.date(2025, 1, 1), recipe=PlannedRecipe(pk=1, name="Carrot Surprise"))
        )

    async def test_two_users_can_plan_same_day(self, client: AsyncClient, user_two_client: AsyncClient, carrots_recipe):
        first_recipe = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        first_recipe.raise_for_status()
        second_recipe = await user_two_client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        second_recipe.raise_for_status()

        first_plan = await client.post(
            "/api/v1/planned_day",
            json={"day": "2025-01-01", "recipe": PlannedRecipe.model_validate(first_recipe.json()).model_dump()},
        )
        second_plan = await user_two_client.post(
            "/api/v1/planned_day",
            json={"day": "2025-01-01", "recipe": PlannedRecipe.model_validate(second_recipe.json()).model_dump()},
        )

        assert first_plan.status_code == status.HTTP_201_CREATED
        assert second_plan.status_code == status.HTTP_201_CREATED
        assert first_plan.json()["pk"] != second_plan.json()["pk"]

    async def test_cannot_plan_another_users_recipe(
        self, client: AsyncClient, user_two_client: AsyncClient, carrots_recipe
    ):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        response.raise_for_status()
        recipe = PlannedRecipe.model_validate(response.json())

        response = await user_two_client.post(
            "/api/v1/planned_day",
            json={"day": "2025-01-01", "recipe": recipe.model_dump()},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

        check = await user_two_client.get(
            "/api/v1/planned_day", params={"start_date": "2025-01-01", "end_date": "2025-01-01"}
        )
        assert check.json() == []

    async def test_get_range(self, client: AsyncClient, carrots_recipe):
        recipe_response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())

        recipe = PlannedRecipe.model_validate(recipe_response.json())

        for day in ["2025-01-01", "2025-02-01", "2025-03-01"]:
            planned_day = PlannedDay(day=dt.date.fromisoformat(day), recipe=recipe)
            response = await client.post("/api/v1/planned_day", json=planned_day.model_dump())
            response.raise_for_status()

        response = await client.get(
            "/api/v1/planned_day", params={"start_date": "2025-01-01", "end_date": "2025-02-20"}
        )
        assert response.status_code == status.HTTP_200_OK

        plan = [PlannedDayResponse.model_validate(d) for d in response.json()]

        assert plan == snap(
            [
                PlannedDayResponse(pk=1, day=dt.date(2025, 1, 1), recipe=PlannedRecipe(pk=1, name="Carrot Surprise")),
                PlannedDayResponse(pk=2, day=dt.date(2025, 2, 1), recipe=PlannedRecipe(pk=1, name="Carrot Surprise")),
            ]
        )

    @time_machine.travel(dt.date(2025, 1, 1))
    async def test_summarise_ignores_other_users_plans(
        self, client: AsyncClient, user_two_client: AsyncClient, db_session, carrots_recipe
    ):
        response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        response.raise_for_status()
        recipe = PlannedRecipe.model_validate(response.json())

        user_two = (await user_two_client.get("/api/v1/users/me")).json()

        # Simulate a cross-user plan stored before this was rejected.
        db_session.add(StoredPlannedDay(day=dt.date(2025, 1, 1), recipe_pk=recipe.pk, user_pk=user_two["pk"]))
        await db_session.flush()

        summary_response = await client.get("/api/v1/planned_day/summary/")
        summary = [RecipeSummary.model_validate(s) for s in summary_response.json()]

        assert summary == [RecipeSummary(name="Carrot Surprise", count=0, last_eaten=None)]

    @time_machine.travel(dt.date(2025, 1, 1))
    async def test_summarise(self, client: AsyncClient, take_away, carrots_recipe):
        recipe_response = await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        response = await client.post("/api/v1/recipes", json=take_away.model_dump())
        response.raise_for_status()

        recipe = PlannedRecipe.model_validate(recipe_response.json())

        # Plan a meal for today and another for a future date: only today's meal counts.
        for day in [dt.date(2025, 1, 1), dt.date(2025, 1, 8)]:
            planned_day = PlannedDay(day=day, recipe=recipe)
            response = await client.post("/api/v1/planned_day", json=planned_day.model_dump())
            response.raise_for_status()

        summary_response = await client.get("/api/v1/planned_day/summary/")

        summary = [RecipeSummary.model_validate(s) for s in summary_response.json()]

        assert summary == snap(
            [
                RecipeSummary(name="Carrot Surprise", count=1, last_eaten=dt.date(2025, 1, 1)),
                RecipeSummary(name="Take Away", count=0, last_eaten=None),
            ]
        )

    @time_machine.travel(dt.date(2025, 1, 1))
    async def test_summarise_filters_by_labels(
        self, client: AsyncClient, burger_recipe, sausage_recipe, carrots_recipe
    ):
        planned_recipes = []
        for recipe in (burger_recipe, sausage_recipe):
            response = await client.post("/api/v1/recipes", json=recipe.model_dump())
            response.raise_for_status()
            planned_recipes.append(PlannedRecipe.model_validate(response.json()))

        unplanned_recipe = carrots_recipe.model_dump() | {
            "name": "Beef Stew",
            "labels": [{"category": "meat", "sub_category": "beef"}],
        }
        response = await client.post("/api/v1/recipes", json=unplanned_recipe)
        response.raise_for_status()

        burger, sausage = planned_recipes
        for recipe, day in [
            (burger, dt.date(2025, 1, 1)),
            (burger, dt.date(2025, 1, 8)),
            (sausage, dt.date(2024, 12, 31)),
        ]:
            response = await client.post("/api/v1/planned_day", json=PlannedDay(day=day, recipe=recipe).model_dump())
            response.raise_for_status()

        response = await client.get("/api/v1/planned_day/summary/", params=[("labels", "meat::beef")])
        summary = [RecipeSummary.model_validate(s) for s in response.json()]
        assert summary == [
            RecipeSummary(name="Beef Stew", count=0, last_eaten=None),
            RecipeSummary(name="Burger", count=1, last_eaten=dt.date(2025, 1, 1)),
        ]

        response = await client.get("/api/v1/planned_day/summary/", params=[("labels", "meat::pork")])
        summary = [RecipeSummary.model_validate(s) for s in response.json()]
        assert summary == [RecipeSummary(name="Sausage Pasta", count=1, last_eaten=dt.date(2024, 12, 31))]

        response = await client.get(
            "/api/v1/planned_day/summary/",
            params=[("labels", "meat::beef"), ("labels", "time::quick")],
        )
        summary = [RecipeSummary.model_validate(s) for s in response.json()]
        assert summary == [RecipeSummary(name="Burger", count=1, last_eaten=dt.date(2025, 1, 1))]

        response = await client.get(
            "/api/v1/planned_day/summary/",
            params=[("labels", "meat::beef"), ("labels", "time::slow")],
        )
        assert response.json() == []

    async def test_summarise_filter_respects_user_scope(
        self, client: AsyncClient, user_two_client: AsyncClient, burger_recipe, sausage_recipe
    ):
        burger_response = await client.post("/api/v1/recipes", json=burger_recipe.model_dump())
        burger_response.raise_for_status()
        sausage_response = await user_two_client.post("/api/v1/recipes", json=sausage_recipe.model_dump())
        sausage_response.raise_for_status()

        burger = PlannedRecipe.model_validate(burger_response.json())
        sausage = PlannedRecipe.model_validate(sausage_response.json())
        for user_client, recipe in ((client, burger), (user_two_client, sausage)):
            response = await user_client.post(
                "/api/v1/planned_day",
                json=PlannedDay(day=dt.date(2025, 1, 1), recipe=recipe).model_dump(),
            )
            response.raise_for_status()

        response = await client.get("/api/v1/planned_day/summary/", params=[("labels", "meat::pork")])
        assert response.json() == []

        response = await user_two_client.get("/api/v1/planned_day/summary/", params=[("labels", "meat::pork")])
        summary = [RecipeSummary.model_validate(s) for s in response.json()]
        assert summary == [RecipeSummary(name="Sausage Pasta", count=1, last_eaten=dt.date(2025, 1, 1))]

    async def test_summarise_rejects_malformed_labels(self, client: AsyncClient):
        response = await client.get("/api/v1/planned_day/summary/", params=[("labels", "bad-label")])

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
