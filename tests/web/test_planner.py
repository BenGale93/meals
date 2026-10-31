from datetime import date, timedelta
from typing import TYPE_CHECKING

import time_machine
from starlette import status

from .assertions import assert_meal_options, assert_page_shell, assert_summary_rows, label_checkbox

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestPlannerAPI:
    async def test_get_plan_page(self, client: AsyncClient):
        response = await client.get("/plan.html")

        assert response.status_code == status.HTTP_200_OK
        assert_page_shell(response)
        assert "Weekly Meal Plan" in response.text
        assert 'hx-get="/weeks_plan"' in response.text
        assert 'hx-get="/summary"' in response.text
        assert "show-success" in response.text
        assert "show-error" in response.text

    @time_machine.travel(date(2020, 1, 1))
    async def test_get_weeks_plan(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        today = date.today()
        response = await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": today.isoformat()})

        assert response.status_code == status.HTTP_200_OK

        response = await client.get("/weeks_plan")

        assert response.status_code == status.HTTP_200_OK
        assert carrots_recipe.name in response.text
        assert today.strftime("%Y-%m-%d") in response.text
        assert f'value="{today.isoformat()}" name="day"' in response.text
        assert 'value="Carrot Surprise"' in response.text
        assert response.text.count('hx-post="/planned_day"') == 7

    async def test_get_meals_like(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        response = await client.get("/meals", params={"meal": "carr"})

        assert response.status_code == status.HTTP_200_OK
        assert_meal_options(response, [carrots_recipe.name])

    async def test_meals_like_empty_string(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        response = await client.get("/meals", params={"meal": ""})

        assert response.status_code == status.HTTP_200_OK
        assert_meal_options(response, [carrots_recipe.name])

    async def test_meals_like_no_match(self, client: AsyncClient):
        response = await client.get("/meals", params={"meal": "nomatch"})

        assert response.status_code == status.HTTP_200_OK
        assert_meal_options(response, [])

    @time_machine.travel(date(2020, 1, 1))
    async def test_update_planned_day(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        today = date.today()
        response = await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": today.isoformat()})
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["HX-Trigger"] == "show-success"

    @time_machine.travel(date(2020, 1, 1))
    async def test_update_planned_day_recipe_not_found(self, client: AsyncClient):
        today = date.today()
        response = await client.post("/planned_day", data={"meal": "something", "day": today.isoformat()})
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["HX-Trigger"] == "show-error"

    async def test_update_planned_day_invalid_date(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        response = await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": "invalid-date"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @time_machine.travel(date(2020, 1, 1))
    async def test_update_planned_day_overwrite(self, client: AsyncClient, carrots_recipe, pasta_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        await client.post("/api/v1/recipes", json=pasta_recipe.model_dump())
        today = date.today()

        # Plan carrots for today
        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": today.isoformat()})

        # Now plan pasta for today, overwriting carrots
        await client.post("/planned_day", data={"meal": pasta_recipe.name, "day": today.isoformat()})

        response = await client.get("/weeks_plan")
        assert pasta_recipe.name in response.text
        assert carrots_recipe.name not in response.text

    async def test_get_summary_table(self, client: AsyncClient):
        response = await client.get("/summary")

        assert response.status_code == status.HTTP_200_OK
        assert_summary_rows(response, [])
        assert "Add labels to your recipes to filter them" in response.text

    async def test_get_summary_table_filter_control(self, client: AsyncClient, burger_recipe, sausage_recipe):
        for recipe in (burger_recipe, sausage_recipe):
            response = await client.post("/api/v1/recipes", json=recipe.model_dump())
            response.raise_for_status()

        response = await client.get("/summary")

        assert response.status_code == status.HTTP_200_OK
        assert 'hx-get="/summary"' in response.text
        assert 'hx-target="#recipe-summary"' in response.text
        assert 'hx-swap="outerHTML"' in response.text
        assert 'hx-trigger="change"' in response.text
        assert 'name="labels"' in response.text
        assert "Clear" in response.text
        assert 'hx-include="closest form"' in response.text
        assert "checked" not in label_checkbox(response.text, "meat::beef")
        assert "Active filters:" not in response.text
        assert 'open=""' not in response.text

    async def test_get_summary_table_filters_rows(self, client: AsyncClient, burger_recipe, sausage_recipe):
        for recipe in (burger_recipe, sausage_recipe):
            response = await client.post("/api/v1/recipes", json=recipe.model_dump())
            response.raise_for_status()

        response = await client.get("/summary", params=[("labels", "meat::beef")])

        assert response.status_code == status.HTTP_200_OK
        assert_summary_rows(response, [(burger_recipe.name, 0, "Never")])
        assert "checked" in label_checkbox(response.text, "meat::beef")
        assert "checked" not in label_checkbox(response.text, "meat::pork")
        assert "Active filters:" in response.text
        assert 'aria-label="Remove filter meat::beef"' in response.text

    async def test_summary_malformed_filter_falls_back(self, client: AsyncClient, burger_recipe, sausage_recipe):
        for recipe in (burger_recipe, sausage_recipe):
            response = await client.post("/api/v1/recipes", json=recipe.model_dump())
            response.raise_for_status()

        response = await client.get("/summary", params=[("labels", "not-a-label")])

        assert response.status_code == status.HTTP_200_OK
        assert_summary_rows(
            response,
            [
                (burger_recipe.name, 0, "Never"),
                (sausage_recipe.name, 0, "Never"),
            ],
        )

    @time_machine.travel(date(2020, 1, 1))
    async def test_get_summary_table_with_recipe(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        today = date.today()
        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": today.isoformat()})
        response = await client.get("/summary")

        assert response.status_code == status.HTTP_200_OK
        assert_summary_rows(response, [(carrots_recipe.name, 1, today.isoformat())])

    @time_machine.travel(date(2020, 1, 1))
    async def test_get_summary_table_multiple_plans(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        today = date.today()
        yesterday = today - timedelta(days=1)

        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": today.isoformat()})
        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": yesterday.isoformat()})

        response = await client.get("/summary")

        assert response.status_code == status.HTTP_200_OK
        assert_summary_rows(response, [(carrots_recipe.name, 2, today.isoformat())])

    @time_machine.travel(date(2020, 1, 1))
    async def test_get_summary_table_unplanned_recipe(self, client: AsyncClient, carrots_recipe, pasta_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        await client.post("/api/v1/recipes", json=pasta_recipe.model_dump())
        today = date.today()

        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": today.isoformat()})

        response = await client.get("/summary")

        assert response.status_code == status.HTTP_200_OK
        assert_summary_rows(response, [(carrots_recipe.name, 1, today.isoformat()), (pasta_recipe.name, 0, "Never")])
