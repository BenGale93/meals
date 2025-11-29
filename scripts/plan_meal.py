"""Plans a meal using the CLI."""  # noqa: INP001

from datetime import date

import typer
from httpx import Client
from rich import print as echo

from meals import schemas

app = typer.Typer()


@app.command()
def plan(name: str, day: str) -> None:
    """Plan a meal for a specific day."""
    parsed_day = date.fromisoformat(day)

    user = schemas.CreateUserRequest(user_name="Ben")
    client = Client(base_url="http://127.0.0.1:8000/api/v1", headers=user.auth_headers())

    recipe_response = client.get("/recipes/", params={"name": name})

    recipe = schemas.PlannedRecipe.model_validate(recipe_response.json())

    planned_day = schemas.PlannedDay(day=parsed_day, recipe=recipe)
    day_json = planned_day.model_dump()
    echo(day_json)
    response = client.post("/planned_day", json=day_json)

    response.raise_for_status()

    echo(response)


if __name__ == "__main__":
    app()
