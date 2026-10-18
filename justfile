default: lint type_check test

alias t := test

@test:
    uv run pytest tests/
    uv run coverage report --fail-under=100

alias tc := type_check

@type_check:
    uv run pyrefly check

alias l := lint

@lint:
    uv run ruff format .
    uv run ruff check . --fix
    uv run lint-imports

@start:
    uv run fastapi dev src/main.py

alias d := deploy

# Deploy on the Pi: verified backup, pull, sync, restart, health check (run on the host).
@deploy:
    bash scripts/deploy.sh

# Side-by-side validation: start [ref] | stop | clean | promote (run on the host).
@candidate action="start" *args:
    bash scripts/candidate.sh {{action}} {{args}}

alias m := migrate

# Apply pending schema migrations to the configured database (honours .env).
@migrate:
    if [ -f .env ]; then uv run --env-file .env alembic upgrade head; else uv run alembic upgrade head; fi

alias b := backup

@backup *args:
    if [ -f .env ]; then uv run --env-file .env python scripts/backup_db.py {{args}}; else uv run python scripts/backup_db.py {{args}}; fi