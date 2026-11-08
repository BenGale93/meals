from datetime import date, timedelta
from typing import TYPE_CHECKING

import time_machine
from starlette import status

from .assertions import assert_meal_options, assert_page_shell, assert_summary_rows, label_checkbox

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestPlannerAPI:
    @time_machine.travel(date(2020, 1, 1))
    async def test_get_plan_page(self, client: AsyncClient):
        response = await client.get("/plan.html")

        assert response.status_code == status.HTTP_200_OK
        assert_page_shell(response)
        assert "Weekly Meal Plan" in response.text
        assert 'id="week-panel"' in response.text
        assert "01 Jan 2020 - 07 Jan 2020" in response.text
        assert 'href="/plan.html?start=2019-12-25"' in response.text
        assert 'hx-get="/weeks_plan?start=2019-12-25"' in response.text
        assert 'href="/plan.html?start=2020-01-08"' in response.text
        assert 'hx-get="/weeks_plan?start=2020-01-08"' in response.text
        assert 'aria-disabled="true"' in response.text
        assert 'aria-current="date"' in response.text
        assert "Wednesday" in response.text
        assert "01 Jan" in response.text
        assert 'hx-get="/summary"' in response.text
        assert "show-success" in response.text
        assert "show-error" in response.text

    @time_machine.travel(date(2020, 1, 5))
    async def test_default_window_starts_today_even_on_sunday(self, client: AsyncClient):
        response = await client.get("/weeks_plan")

        assert response.status_code == status.HTTP_200_OK
        assert response.text.count('hx-post="/planned_day"') == 7
        assert response.text.count('aria-current="date"') == 1
        for offset in range(7):
            day = date(2020, 1, 5) + timedelta(days=offset)
            assert f'value="{day.isoformat()}" name="day"' in response.text

        assert 'value="2020-01-04" name="day"' not in response.text

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

    async def test_weeks_plan_uses_exact_start_date(self, client: AsyncClient):
        response = await client.get("/weeks_plan", params={"start": "2020-01-01"})

        assert response.status_code == status.HTTP_200_OK
        assert "01 Jan 2020 - 07 Jan 2020" in response.text
        assert 'value="2020-01-01" name="day"' in response.text
        assert 'value="2020-01-07" name="day"' in response.text
        assert 'value="2019-12-30" name="day"' not in response.text

    @time_machine.travel(date(2020, 1, 1))
    async def test_week_navigation_links(self, client: AsyncClient):
        response = await client.get("/weeks_plan")

        assert response.status_code == status.HTTP_200_OK
        assert 'href="/plan.html?start=2019-12-25"' in response.text
        assert 'hx-get="/weeks_plan?start=2019-12-25"' in response.text
        assert 'href="/plan.html?start=2020-01-08"' in response.text
        assert 'hx-get="/weeks_plan?start=2020-01-08"' in response.text
        assert 'hx-target="#week-panel"' in response.text
        assert 'hx-swap="outerHTML"' in response.text
        assert 'hx-push-url="true"' in response.text
        assert 'aria-disabled="true"' in response.text

    @time_machine.travel(date(2020, 1, 1))
    async def test_today_control_links_back_when_window_starts_elsewhere(self, client: AsyncClient):
        response = await client.get("/weeks_plan", params={"start": "2019-12-30"})

        assert response.status_code == status.HTTP_200_OK
        assert 'href="/plan.html"' in response.text
        assert 'hx-get="/weeks_plan?start=2020-01-01"' in response.text
        assert 'aria-disabled="true"' not in response.text
        assert response.text.count('aria-current="date"') == 1

    @time_machine.travel(date(2020, 1, 1))
    async def test_plans_are_scoped_to_the_viewed_window(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        future = date(2020, 1, 8)
        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": future.isoformat()})

        current = await client.get("/weeks_plan")
        future_window = await client.get("/weeks_plan", params={"start": future.isoformat()})

        assert carrots_recipe.name not in current.text
        assert carrots_recipe.name in future_window.text
        assert 'value="2020-01-08" name="day"' in future_window.text

    async def test_invalid_start_returns_422(self, client: AsyncClient):
        for path in ("/plan.html", "/weeks_plan"):
            response = await client.get(path, params={"start": "not-a-date"})

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @time_machine.travel(date(2020, 1, 1))
    async def test_clear_planned_day_re_renders_same_window(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": "2020-01-03"})

        response = await client.post("/planned_day/clear", params={"start": "2020-01-01"}, data={"day": "2020-01-03"})

        assert response.status_code == status.HTTP_200_OK
        assert 'id="week-panel"' in response.text
        assert "01 Jan 2020 - 07 Jan 2020" in response.text
        assert 'hx-post="/planned_day/clear' not in response.text
        assert carrots_recipe.name not in response.text
        assert 'value="2020-01-03" name="day"' in response.text

    @time_machine.travel(date(2020, 1, 1))
    async def test_clear_preserves_viewed_window(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": "2020-01-10"})

        response = await client.post("/planned_day/clear", params={"start": "2020-01-08"}, data={"day": "2020-01-10"})

        assert response.status_code == status.HTTP_200_OK
        assert "08 Jan 2020 - 14 Jan 2020" in response.text
        assert 'value="2020-01-08" name="day"' in response.text
        assert 'value="2020-01-10" name="day"' in response.text
        assert carrots_recipe.name not in response.text

    @time_machine.travel(date(2020, 1, 1))
    async def test_clear_unplanned_day_is_idempotent(self, client: AsyncClient):
        response = await client.post("/planned_day/clear", params={"start": "2020-01-01"}, data={"day": "2020-01-01"})

        assert response.status_code == status.HTTP_200_OK
        assert 'id="week-panel"' in response.text
        assert 'value="2020-01-01" name="day"' in response.text

    @time_machine.travel(date(2020, 1, 1))
    async def test_clear_does_not_affect_another_users_plan(
        self, client: AsyncClient, user_two_client: AsyncClient, carrots_recipe
    ):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": "2020-01-01"})

        response = await user_two_client.post(
            "/planned_day/clear", params={"start": "2020-01-01"}, data={"day": "2020-01-01"}
        )

        assert response.status_code == status.HTTP_200_OK
        response = await client.get("/weeks_plan")
        assert carrots_recipe.name in response.text

    @time_machine.travel(date(2020, 1, 1))
    async def test_clear_button_only_on_planned_rows(self, client: AsyncClient, carrots_recipe):
        empty = await client.get("/weeks_plan")
        assert 'hx-post="/planned_day/clear' not in empty.text

        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": "2020-01-01"})

        planned = await client.get("/weeks_plan")
        assert planned.text.count('hx-post="/planned_day/clear') == 1

    async def test_clear_requires_start_and_day(self, client: AsyncClient):
        missing_start = await client.post("/planned_day/clear", data={"day": "2020-01-01"})
        missing_day = await client.post("/planned_day/clear", params={"start": "2020-01-01"})

        assert missing_start.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert missing_day.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_clear_requires_auth(self, bad_client: AsyncClient):
        response = await bad_client.post(
            "/planned_day/clear", params={"start": "2020-01-01"}, data={"day": "2020-01-01"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

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
