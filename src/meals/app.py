"""Main entry point of the meals app."""

from fastapi import FastAPI

from meals.api.v1.routes import router as v1_router
from meals.error_handlers import register_exception_handlers
from meals.logging_config import configure_logging
from meals.middleware import RequestContextMiddleware
from meals.web.core import router as view_router


def create_app() -> FastAPI:
    """Build the application, including logging, middleware and error handlers."""
    configure_logging()

    app = FastAPI(title="Meals")
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    # The schema is owned by Alembic (see migrations/). The app deliberately does not
    # create tables at start-up: run `alembic upgrade head` (or `just migrate`) before
    # starting it, so pointing at the wrong database fails loudly instead of quietly
    # creating an empty one.
    app.include_router(v1_router, prefix="/api")
    app.include_router(view_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        """For checking the health of the server."""
        return {"status": "ok", "message": "Server is running."}

    return app


app = create_app()
