"""Populates the DB with the content of a YAML file."""  # noqa: INP001

import asyncio
from pathlib import Path

from pydantic_yaml import parse_yaml_file_as

from meals import crud, schemas
from meals.database import async_session, init_models


async def main() -> None:
    """Adds the recipes define in the YAML file to database."""
    recipes = parse_yaml_file_as(schemas.Recipes, Path("recipes.yaml"))

    await init_models()
    async with async_session() as session, session.begin():
        _ = [await crud.create_recipes(session, r) for r in recipes]

        print(await crud.get_all_recipes(session))  # noqa: T201


if __name__ == "__main__":
    asyncio.run(main())
