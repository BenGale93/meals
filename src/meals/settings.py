"""Application settings, read from the environment."""

import os

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///meals.db"


def database_url() -> str:
    """Return the configured database URL.

    Defaults to a relative SQLite file so development needs no configuration; set
    ``DATABASE_URL`` (see ``.env.example``) to point at the real database.
    """
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
