"""Main entry point of the meals app."""

import typing as t
from contextlib import asynccontextmanager

from fastapi import FastAPI

from meals.api.v1.routes import router as v1_router
from meals.database.session import init_models
from meals.web.core import router as view_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> t.AsyncGenerator[t.Any]:  # noqa: ARG001
    """Run tasks before and after the server starts."""
    await init_models()
    yield


app = FastAPI(title="Meals", lifespan=lifespan)

app.include_router(v1_router, prefix="/api")
app.include_router(view_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """For checking the health of the server."""
    return {"status": "ok", "message": "Server is running."}
