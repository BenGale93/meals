"""Populates the DB with the content of a YAML file."""  # noqa: INP001

import asyncio
from pathlib import Path

from httpx import AsyncClient
from pydantic_yaml import parse_yaml_file_as
from rich import print as echo

from meals import schemas


async def main() -> None:
    """Adds the recipes define in the YAML file to database."""
    recipes = parse_yaml_file_as(schemas.CreateRecipes, Path("recipes.yaml"))

    client = AsyncClient(base_url="http://127.0.0.1:8000/api/v1")

    results = [await client.post("/recipes", json=r.model_dump()) for r in recipes]

    echo(results)


if __name__ == "__main__":
    asyncio.run(main())
