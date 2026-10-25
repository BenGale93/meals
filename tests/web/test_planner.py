from datetime import date, timedelta
from typing import TYPE_CHECKING

import time_machine
from inline_snapshot import external
from starlette import status

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestPlannerAPI:
    async def test_get_plan_page(self, client: AsyncClient):
        response = await client.get("/plan.html")

        assert response.status_code == status.HTTP_200_OK
        assert response.text == external("uuid:6b3bec63-ac97-44ef-bf76-29922cffce88.txt")

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
        assert response.text == external("uuid:ebe86d54-196e-4401-ae8a-a7738a8f302e.txt")

    async def test_get_meals_like(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        response = await client.get("/meals", params={"meal": "carr"})

        assert response.status_code == status.HTTP_200_OK
        assert response.text == external("uuid:6ef373f6-1019-4d22-bd09-a0c745a76cb4.txt")

    async def test_meals_like_empty_string(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        response = await client.get("/meals", params={"meal": ""})

        assert response.status_code == status.HTTP_200_OK
        assert response.text == external("uuid:d74c18ec-7300-4d4c-b858-f08ecf9672f9.txt")

    async def test_meals_like_no_match(self, client: AsyncClient):
        response = await client.get("/meals", params={"meal": "nomatch"})

        assert response.status_code == status.HTTP_200_OK
        assert response.text == external("uuid:a0b193ca-c6a8-4051-b067-a1e4bd0b5997.txt")

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
        assert response.text == external("uuid:fcdd9952-417d-4282-aea9-9fb83decbe44.txt")

    @time_machine.travel(date(2020, 1, 1))
    async def test_get_summary_table_with_recipe(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        today = date.today()
        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": today.isoformat()})
        response = await client.get("/summary")

        assert response.status_code == status.HTTP_200_OK
        assert carrots_recipe.name in response.text
        assert "1" in response.text
        assert today.isoformat() in response.text

    @time_machine.travel(date(2020, 1, 1))
    async def test_get_summary_table_multiple_plans(self, client: AsyncClient, carrots_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        today = date.today()
        yesterday = today - timedelta(days=1)

        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": today.isoformat()})
        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": yesterday.isoformat()})

        response = await client.get("/summary")

        assert response.status_code == status.HTTP_200_OK
        assert carrots_recipe.name in response.text
        assert "2" in response.text
        assert today.isoformat() in response.text

    @time_machine.travel(date(2020, 1, 1))
    async def test_get_summary_table_unplanned_recipe(self, client: AsyncClient, carrots_recipe, pasta_recipe):
        await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
        await client.post("/api/v1/recipes", json=pasta_recipe.model_dump())
        today = date.today()

        await client.post("/planned_day", data={"meal": carrots_recipe.name, "day": today.isoformat()})

        response = await client.get("/summary")

        assert response.status_code == status.HTTP_200_OK
        assert response.text == external("uuid:d5f95a03-1289-49bc-adcb-4bdd63929b72.txt")
