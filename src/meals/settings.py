"""Application settings, read from the environment."""

import logging
import os

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///meals.db"


def database_url() -> str:
    """Return the configured database URL.

    Defaults to a relative SQLite file so development needs no configuration; set
    ``DATABASE_URL`` (see ``.env.example``) to point at the real database.
    """
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def log_level() -> int:
    """Return the configured logging level.

    Set ``LOG_LEVEL`` (e.g. ``DEBUG``) to change it; anything unrecognised falls
    back to ``INFO`` so a typo cannot silence the logs.
    """
    name = os.environ.get("LOG_LEVEL", "INFO").upper()
    return logging.getLevelNamesMapping().get(name, logging.INFO)
