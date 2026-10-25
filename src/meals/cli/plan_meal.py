"""Plan a meal on a running meals server from the command line."""

import asyncio
from datetime import date
from typing import Annotated

import httpx
import typer
from rich import print as echo

from meals.schemas import CreateUserRequest, PlannedDay, PlannedRecipe

DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1"
DEFAULT_USER_NAME = "Ben"

app = typer.Typer()


def _client(base_url: str, headers: dict[str, str]) -> httpx.AsyncClient:
    """Build the authenticated HTTP client used to talk to the API."""
    return httpx.AsyncClient(base_url=base_url, headers=headers)


async def plan_meal(client: httpx.AsyncClient, name: str, day: date) -> None:
    """Plan the named recipe on the given day."""
    response = await client.get("/recipes/", params={"name": name})
    if response.status_code == httpx.codes.NOT_FOUND:
        echo(f"[red]No recipe named {name!r}.[/red]")
        raise typer.Exit(code=1)
    response.raise_for_status()

    recipe = PlannedRecipe.model_validate(response.json())
    planned_day = PlannedDay(day=day, recipe=recipe)
    response = await client.post("/planned_day", json=planned_day.model_dump())
    response.raise_for_status()

    echo(f"Planned [bold]{recipe.name}[/bold] for {planned_day.day.isoformat()}.")


async def _run(base_url: str, name: str, day: str, user_name: str) -> None:
    """Look the recipe up and plan it through the API."""
    user = CreateUserRequest(user_name=user_name)
    async with _client(base_url, user.auth_headers()) as client:
        await plan_meal(client, name, date.fromisoformat(day))


@app.command()
def plan(
    name: str,
    day: str,
    base_url: Annotated[str, typer.Option(help="Base URL of the API of a running server.")] = DEFAULT_BASE_URL,
    user_name: Annotated[str, typer.Option(help="User planning the meal.")] = DEFAULT_USER_NAME,
) -> None:
    """Plan a meal by name for a date (YYYY-MM-DD)."""
    asyncio.run(_run(base_url, name, day, user_name))
