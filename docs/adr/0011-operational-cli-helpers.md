# 0011: Send seed and plan helpers through the running API

- Status: Accepted
- Date: 2026-11-13

## Context

`meals-seed` and `meals-plan` are operational helpers, not application routes. They load seed
data, create a user, plan a meal, or update timings on a development server or the Pi. The app
already owns validation, authentication, user scoping, transactions, and the database session
through its HTTP API.

Backups are different. They need the SQLite file itself, must work while the service is running,
and have no API endpoint.

The helpers need a rule for when to call the API and when to work on the database file directly.
Using the same path as a browser or API client avoids a second implementation of the data model,
but file-level operations cannot go through the API.

## Decision

### API-backed helpers

- Install `meals-seed` and `meals-plan` from `src/meals/cli/` as console scripts. They call a
  running server with `httpx.AsyncClient` and do not create a database session or import the
  repositories or services.
- Default to `http://127.0.0.1:8000/api/v1` and the user `Ben`; `--base-url` and `--user-name`
  override both.
- Reuse the API request schemas and `CreateUserRequest.auth_headers()`. The helpers therefore
  send the same payloads and placeholder Basic auth as any other API client.
- `meals-seed` loads YAML through `pydantic-yaml` and the shared schemas. It creates the user if
  absent, posts each recipe, and patches the timings. A duplicate user or recipe is reported and
  skipped; timings are upserted. Re-running does not update existing recipes or backfill labels.
- `meals-plan` looks the recipe up by name, builds a `PlannedDay`, and posts it to
  `/planned_day`. A missing recipe exits with status 1.
- Use Typer for the command surface and Rich for the messages. These are existing dependencies,
  not a second application framework.
- The API path exercises authentication, validation, user scoping, and transactions. It also
  keeps the API process as the only writer to the live SQLite file.

### File-backed backup

- Keep backup in `scripts/backup_db.py`, run through `just backup`. It is a host operation with
  filesystem access, not an installed API client.
- Resolve the source from `meals.settings.database_url()` and refuse a non-file or in-memory URL.
  Open the source read-only, write the target with SQLite's online backup API, and verify the
  copy by reopening it read-only and printing every table's row count.
- Default the target to `<database dir>/backups/<stem>-<timestamp>.db`. A positional directory,
  `BACKUP_DIR`, or `--to` can change it. Refuse to write a backup over its source.
- `just backup` loads `.env` when present so the script and the service use the same database.
- Do not add a backup endpoint to the API. The operation needs the database file, and exposing
  it as an HTTP route would widen the API without removing the need for host filesystem access.

## Consequences

- The helpers do not duplicate repository queries, session setup, or validation. A change to the
  API contract reaches them through the shared schemas.
- They need a running server and valid credentials. They cannot seed or plan while the service
  is down.
- The placeholder Basic auth means the helpers send a dummy password. Real authentication would
  require a password or token option.
- Seeding is safe to repeat for users, recipes, and timings, but it is not an update or migration
  tool. Existing recipes and their labels are left alone.
- Backup is independent of the API and can run while the service is live because it uses the
  online backup API. Restore remains a separate manual operation with the service stopped.
- The CLI modules sit outside the application layers. The app does not import them, and the
  import-linter contract keeps core modules from reaching into `meals.cli`.

## Alternatives considered

- **Call repositories or services directly from the seed and plan helpers**: rejected because it
  would bypass authentication, validation, user scoping, and request transactions, duplicate
  session setup, and create a second writer when the service is running.
- **Run seeding at application start-up**: rejected because seed files are external, optional,
  and not present on every host. Start-up should not depend on the seed data.
- **Add API endpoints for backup and restore**: rejected because backup needs the database file
  and host filesystem access. The API would not remove that requirement.
- **Back up with `cp` or the `sqlite3` shell**: rejected because a live copy can be inconsistent
  and can miss the `-wal` and `-shm` files. The online backup API gives one consistent snapshot.
- **Generate an OpenAPI client for the helpers**: rejected because they use a few endpoints and
  already share the request schemas. A generated client would add a build step for little gain.
- **Make backup a `meals-*` console script**: rejected because it is a host operation tied to the
  database path and `.env`, and `just backup` is already the operational entry point.
