"""Tests for the command-line helpers."""

import json
from datetime import date
from typing import TYPE_CHECKING

import httpx
import pytest
import typer
from httpx import ASGITransport, AsyncClient, MockTransport, Request, Response
from typer.testing import CliRunner

from meals.cli import plan_meal as plan_meal_cli
from meals.cli import populate_db as populate_db_cli

if TYPE_CHECKING:
    from pathlib import Path

RECIPES_YAML = """\
- name: Carrot Surprise
  ingredients:
    - Carrot 10 units
  instructions: Test instructions
  labels:
    - category: vegetable
      sub_category: carrot
"""

PLAIN_RECIPES_YAML = """\
- name: Carrot Surprise
  ingredients:
    - Carrot 10 units
  instructions: Test instructions
"""

TIMINGS_YAML = """\
finish_time: "18:00"
steps:
  - description: Start
    offset: -60
  - description: Finish
    offset: 0
"""


@pytest.fixture
def seed_files(tmp_path: Path) -> tuple[Path, Path]:
    recipes = tmp_path / "recipes.yaml"
    recipes.write_text(RECIPES_YAML)
    timings = tmp_path / "timings.yaml"
    timings.write_text(TIMINGS_YAML)
    return recipes, timings


async def test_seed_creates_recipes_and_timings(test_app, user_one, tmp_path):
    recipes_path = tmp_path / "recipes.yaml"
    recipes_path.write_text(PLAIN_RECIPES_YAML)
    timings_path = tmp_path / "timings.yaml"
    timings_path.write_text(TIMINGS_YAML)
    recipes = populate_db_cli.load_recipes(recipes_path)
    timings = populate_db_cli.load_timings(timings_path)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/api/v1") as client:
        await populate_db_cli.seed(client, recipes, timings, user_one)
        # The second run proves the script is safe to repeat: the user and recipe exist.
        await populate_db_cli.seed(client, recipes, timings, user_one)

        headers = user_one.auth_headers()
        recipes_response = await client.get("/recipes", headers=headers)
        timings_response = await client.get("/timings", headers=headers)

    assert [recipe["name"] for recipe in recipes_response.json()] == ["Carrot Surprise"]
    assert timings_response.json()["finish_time"] == "18:00:00"
    assert [step["description"] for step in timings_response.json()["steps"]] == ["Start", "Finish"]


async def test_seed_creates_labelled_recipes_and_remains_idempotent(test_app, user_one, tmp_path):
    recipes_path = tmp_path / "recipes.yaml"
    recipes_path.write_text(RECIPES_YAML)
    timings_path = tmp_path / "timings.yaml"
    timings_path.write_text(TIMINGS_YAML)
    recipes = populate_db_cli.load_recipes(recipes_path)
    timings = populate_db_cli.load_timings(timings_path)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/api/v1") as client:
        await populate_db_cli.seed(client, recipes, timings, user_one)
        await populate_db_cli.seed(client, recipes, timings, user_one)

        headers = user_one.auth_headers()
        recipes_response = await client.get("/recipes", headers=headers)

    assert len(recipes_response.json()) == 1
    assert recipes_response.json()[0]["name"] == "Carrot Surprise"
    assert recipes_response.json()[0]["labels"] == [{"category": "vegetable", "sub_category": "carrot"}]


async def test_client_factories():
    async with populate_db_cli._client("http://test/api/v1") as client:  # noqa: SLF001 - the factory is the unit
        assert str(client.base_url) == "http://test/api/v1/"

    async with plan_meal_cli._client("http://test/api/v1", {"Authorization": "Basic test"}) as client:  # noqa: SLF001
        assert client.headers["Authorization"] == "Basic test"


def test_seed_command(monkeypatch, seed_files):
    recipes_path, timings_path = seed_files
    requested: list[tuple[str, str]] = []
    recipe_payloads: list[dict[str, object]] = []

    def handler(request: Request) -> Response:
        requested.append((request.method, request.url.path))
        if request.url.path == "/api/v1/recipes":
            recipe_payloads.append(json.loads(request.content))
        status_code = {
            "/api/v1/users": httpx.codes.CREATED,
            "/api/v1/recipes": httpx.codes.CREATED,
            "/api/v1/timings": httpx.codes.OK,
        }[request.url.path]
        return Response(status_code)

    monkeypatch.setattr(
        populate_db_cli,
        "_client",
        lambda base_url: AsyncClient(transport=MockTransport(handler), base_url=base_url),
    )

    result = CliRunner().invoke(
        populate_db_cli.app,
        [
            "--recipes",
            str(recipes_path),
            "--timings",
            str(timings_path),
            "--base-url",
            "http://test/api/v1",
            "--user-name",
            "Ben",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Labels are not supported by the API yet" not in result.output
    assert recipe_payloads[0]["labels"] == [{"category": "vegetable", "sub_category": "carrot"}]
    assert requested == [
        ("POST", "/api/v1/users"),
        ("POST", "/api/v1/recipes"),
        ("PATCH", "/api/v1/timings"),
    ]


async def test_plan_meal(test_app, client, user_one, carrots_recipe):
    await client.post("/api/v1/recipes", json=carrots_recipe.model_dump())
    planned_on = date(2026, 10, 25)

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test/api/v1",
        headers=user_one.auth_headers(),
    ) as api:
        await plan_meal_cli.plan_meal(api, "Carrot Surprise", planned_on)

        with pytest.raises(typer.Exit) as exc_info:
            await plan_meal_cli.plan_meal(api, "Missing Recipe", planned_on)

    response = await client.get(
        "/api/v1/planned_day",
        params={"start_date": planned_on.isoformat(), "end_date": planned_on.isoformat()},
    )

    assert exc_info.value.exit_code == 1
    assert response.json()[0]["recipe"]["name"] == "Carrot Surprise"


def test_plan_command(monkeypatch):
    requested: list[tuple[str, str]] = []

    def handler(request: Request) -> Response:
        requested.append((request.method, request.url.path))
        if request.method == "GET":
            return Response(
                httpx.codes.OK,
                json={"pk": 1, "name": "Carrot Surprise", "ingredients": [], "instructions": ""},
            )
        return Response(httpx.codes.CREATED, json={})

    monkeypatch.setattr(
        plan_meal_cli,
        "_client",
        lambda base_url, headers: AsyncClient(transport=MockTransport(handler), base_url=base_url, headers=headers),
    )

    result = CliRunner().invoke(
        plan_meal_cli.app,
        ["Carrot Surprise", "2026-10-25", "--base-url", "http://test/api/v1", "--user-name", "Ben"],
    )

    assert result.exit_code == 0, result.output
    assert requested == [
        ("GET", "/api/v1/recipes/"),
        ("POST", "/api/v1/planned_day"),
    ]
