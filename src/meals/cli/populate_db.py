"""Seed a running meals server with recipes and roast timings from YAML."""

import asyncio
from pathlib import Path
from typing import Annotated

import httpx
import typer
from pydantic import RootModel
from pydantic_yaml import parse_yaml_file_as
from rich import print as echo

from meals.schemas import CreateRecipeRequest, CreateUserRequest, TimingsCreate

DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1"
DEFAULT_USER_NAME = "Ben"

app = typer.Typer()


class SeedRecipes(RootModel[list[CreateRecipeRequest]]):
    """The recipes in a seed file."""


def load_recipes(path: Path) -> list[CreateRecipeRequest]:
    """Load and validate the recipes."""
    return parse_yaml_file_as(SeedRecipes, path).root


def load_timings(path: Path) -> TimingsCreate:
    """Load and validate the roast timings."""
    return parse_yaml_file_as(TimingsCreate, path)


def _client(base_url: str) -> httpx.AsyncClient:
    """Build the HTTP client used to talk to the API."""
    return httpx.AsyncClient(base_url=base_url)


async def seed(
    client: httpx.AsyncClient,
    recipes: list[CreateRecipeRequest],
    timings: TimingsCreate,
    user: CreateUserRequest,
) -> None:
    """Create the user if needed, then seed the recipes and timings.

    Recipes that already exist are skipped by name, so re-running is idempotent but does not
    backfill or update labels on existing recipes.
    """
    response = await client.post("/users", json=user.model_dump())
    if response.status_code == httpx.codes.CONFLICT:
        echo(f"User {user.user_name!r} already exists; reusing it.")
    else:
        response.raise_for_status()

    headers = user.auth_headers()
    created = 0
    for recipe in recipes:
        response = await client.post("/recipes", json=recipe.model_dump(), headers=headers)
        if response.status_code == httpx.codes.CONFLICT:
            echo(f"Recipe {recipe.name!r} already exists; skipping it.")
            continue
        response.raise_for_status()
        created += 1

    response = await client.patch("/timings", json=timings.model_dump(), headers=headers)
    response.raise_for_status()

    echo(f"Seeded {created} recipe(s) and the roast timings for [bold]{user.user_name}[/bold].")


async def _run(base_url: str, recipes: Path, timings: Path, user_name: str) -> None:
    """Load the files and seed them through the API."""
    user = CreateUserRequest(user_name=user_name)
    async with _client(base_url) as client:
        await seed(client, load_recipes(recipes), load_timings(timings), user)


@app.command()
def main(
    recipes: Annotated[str, typer.Option(help="YAML file of recipes to seed.")] = "recipes.yaml",
    timings: Annotated[str, typer.Option(help="YAML file of roast timings to seed.")] = "timings.yaml",
    base_url: Annotated[str, typer.Option(help="Base URL of the API of a running server.")] = DEFAULT_BASE_URL,
    user_name: Annotated[str, typer.Option(help="User to seed the data for.")] = DEFAULT_USER_NAME,
) -> None:
    """Seed a running meals server from YAML files.

    Existing recipes are skipped by name, so re-running is safe but does not update them.
    """
    asyncio.run(_run(base_url, Path(recipes), Path(timings), user_name))
