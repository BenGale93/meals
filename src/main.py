"""Main entry point of the meals app."""

import typing as t
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fasthx.htmy import HTMY
from htmy import Component, html
from sqlalchemy.ext.asyncio import AsyncSession

from meals import crud, schemas
from meals.database import get_db, init_models

SessionDep = t.Annotated[AsyncSession, Depends(get_db)]


@asynccontextmanager
async def lifespan(app: FastAPI) -> t.AsyncGenerator[t.Any]:  # noqa: ARG001
    """Run tasks before and after the server starts."""
    await init_models()
    yield


app = FastAPI(lifespan=lifespan)

htmy = HTMY(
    # Register a request processor that adds a user-agent key to the htmy context.
    request_processors=[
        lambda request: {"user-agent": request.headers.get("user-agent")},
    ]
)


def index_page(_: t.Any) -> Component:
    """The HTML of the index page of the app."""
    return (
        html.DOCTYPE.html,
        html.html(
            html.head(
                # Some metadata
                html.title("FastHX + HTMY example"),
                html.meta.charset(),
                html.meta.viewport(),
                # TailwindCSS
                html.script(src="https://cdn.tailwindcss.com"),
                # HTMX
                html.script(src="https://unpkg.com/htmx.org@2.0.2"),
            ),
            html.div(hx_get="/recipes", hx_trigger="load", hx_swap="outerHTML"),
        ),
    )


@app.get("/")
@htmy.page(index_page)
async def index() -> None:
    """The index page of the application."""


@app.get("/health")
async def health() -> dict[str, str]:
    """For checking the health of the server."""
    return {"status": "ok", "message": "Server is running."}


@app.get("/recipes")
@htmy.hx(schemas.recipes_div)
async def get_all_recipes(session: SessionDep) -> schemas.Recipes:
    """Gets all the recipes."""
    return await crud.get_all_recipes(session)


@app.get("/recipes/{name}")
async def get_recipe(name: str, session: SessionDep) -> schemas.Recipe | None:
    """Gets a recipe with a given name."""
    return await crud.get_recipe(session, name)
