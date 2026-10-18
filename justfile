default: lint type_check test

alias t := test

@test:
    uv run pytest tests/
    uv run coverage report --fail-under=100

alias tc := type_check

@type_check:
    uv run mypy src/ tests/ --config-file=pyproject.toml

alias l := lint

@lint:
    uv run ruff format .
    uv run ruff check . --fix
    uv run lint-imports

@start:
    uv run fastapi dev src/main.py

alias m := migrate

# Apply pending schema migrations to the configured database (honours .env).
@migrate:
    if [ -f .env ]; then uv run --env-file .env alembic upgrade head; else uv run alembic upgrade head; fi

alias b := backup

@backup *args:
    if [ -f .env ]; then uv run --env-file .env python scripts/backup_db.py {{args}}; else uv run python scripts/backup_db.py {{args}}; fi