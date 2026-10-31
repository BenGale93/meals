# Meals

A Python web app for managing the recipes you cook.

## Features

A recipe view for editing existing recipes, and adding new recipes. Recipes can carry
`category::sub_category` labels, edited with an autocomplete chip input, and the recipe list
can be filtered by them.

A meal planning view for planning the weeks meals, seeing what you've eaten
recently/not so recently. Its recipe summary can also be filtered by label.

A Roast timer view, for planning the timings of roast dinners.

## Requirements

- Python 3.14 or newer — `uv` reads `.python-version` and installs it if needed.
- [uv](https://docs.astral.sh/uv/) for dependency management and every `just` recipe.
- [just](https://github.com/casey/just) for the common workflows.
- No Node/npm build step: the UI is server-rendered with
  [htmy](https://github.com/volfpeter/htmy), and Tailwind/HTMX/Alpine are loaded from pinned
  CDN versions (see [Development](#development)).
- SQLite is part of Python. In production the database is a single file outside the
  checkout.

## Setup

```bash
git clone <repository> meals
cd meals
uv sync            # create .venv and install runtime + development dependencies
just migrate       # create/upgrade the schema with Alembic
just start         # dev server on http://127.0.0.1:8000
```

By default the app uses the relative `sqlite+aiosqlite:///meals.db` in the checkout
(gitignored), so local development needs no configuration. The repository root also contains
the optional seed data used by `meals-seed` (`recipes.yaml` is gitignored, `timings.yaml` is
committed); see [Seeding and CLI helpers](#seeding-and-cli-helpers).

### Configuration

Settings come from environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite+aiosqlite:///meals.db` | SQLAlchemy URL; use four slashes for an absolute path (`sqlite+aiosqlite:////home/galeb/meals-data/meals.db`) |
| `LOG_LEVEL` | `INFO` | Structured log verbosity (`DEBUG`, `WARNING`, …) |

The app itself does not read `.env`; systemd loads it via `EnvironmentFile=`, and the
`just migrate`/`just backup` recipes pass it with `uv run --env-file .env`. On the Pi the file
is `/home/galeb/meals/.env` (gitignored; `.env.example` documents it) and holds the absolute
`DATABASE_URL`. For local development either keep the default or export the variable before
`just start`. Details and the live paths are in [`deploy/README.md`](deploy/README.md).

## Development

```bash
just            # lint + type-check + test (run this before committing)
just lint       # ruff format, ruff check --fix, import-linter contracts
just type_check # pyrefly in strict mode (alias: just tc)
just test       # pytest, then the 100% branch-coverage gate (alias: just t)
just start      # FastAPI dev server with reload on http://127.0.0.1:8000
```

Run one test with `uv run pytest tests/api/test_recipes.py::TestRecipesAPI::test_create_and_get_recipe` (add
`-p no:randomly` when debugging order-dependent failures). Tests use a throwaway SQLite file
per test and never touch the configured database; HTTP/HTML snapshots are written with
`inline-snapshot` and updated with `--inline-snapshot=fix` after reviewing the new output.

Alembic owns the schema (`migrations/`); the app does not create tables at start-up. After
changing `src/meals/database/models.py`, generate a migration with
`uv run alembic revision --autogenerate -m "describe the change"`, and apply pending ones
with `just migrate`.

Front-end assets in `src/meals/web/core.py` are pinned to exact CDN versions (Tailwind
3.4.19, HTMX 2.0.2, Alpine 3.17.5) so a CDN release cannot silently change the page. There is
no vendored asset build; if CDN access ever becomes a problem, vendor those three files and
serve them from `FastAPI` instead.

## Seeding and CLI helpers

Both helpers talk to a **running** server (start one with `just start`) and are installed as
console scripts:

```bash
uv run meals-seed                         # POST recipes.yaml and timings.yaml to :8000
uv run meals-plan "Beef Stew" 2026-10-26  # plan a meal by name
```

They use the API at `http://127.0.0.1:8000/api/v1` and authenticate as `Ben`; pass
`--base-url`/`--user-name` to change that. Seeding is repeatable: an existing user or recipe
is reported and skipped, and the roast timings are upserted. `recipes.yaml` is not committed
(it is gitignored). Labels in it are created and linked when a recipe is first inserted;
existing recipes are skipped, so re-seeding does not backfill labels onto them. The database
backup helper stays in `scripts/backup_db.py` (`just backup`) because it works directly on
SQLite without a running server.

## Deployment

The app runs as a systemd service on the Pi. Releases are deployed **on the Pi** with:

```bash
DRY_RUN=1 just deploy   # show the plan
just deploy
```

That takes a verified backup, fast-forwards the checkout, syncs dependencies, restarts the
service (the unit runs `alembic upgrade head` first) and waits for `/health`. For a risky
release (schema change), `just candidate` starts a side-by-side copy on `:8001` against a
database copy, and `just candidate promote` performs the cutover. Nothing rolls back
automatically: on failure the scripts print the status, logs and rollback steps.

To undo a release by hand, stop the service, `git switch --detach <previous commit>`,
`uv sync --frozen`, restart, and restore the pre-cutover database if the migration was not
backward-compatible. Full unit files, configuration, safety rules, the candidate checklist
and the step-by-step rollback/restore procedure are in
[`deploy/README.md`](deploy/README.md). Logs are at `journalctl -u meals -f`.

## Backups and restore

The database is a single SQLite file, so backups are a file copy made through SQLite's online
backup API (safe while the app runs, unlike `cp`):

```bash
just backup              # write to <database dir>/backups, honouring .env
just backup /some/dir    # explicit destination
BACKUP_DIR=/some/dir just backup
```

`just backup` prints the row count of every table so you can confirm the copy is complete.
Keep at least one copy off the Pi. Restore with the service stopped (SQLite allows one
writer), then remove any stale `-wal`/`-shm` sidecars before starting:

```bash
sudo systemctl stop meals
cp <backup> <database path>
rm -f <database path>-wal <database path>-shm
sudo systemctl start meals
```

A backup is a point-in-time snapshot: take a fresh one before every migration or deploy
rather than reusing an old copy.

## Logging

The app writes one JSON object per line to stdout, which systemd captures in journald:

```bash
journalctl -u meals -f
journalctl -u meals -f | jq .            # if jq is installed
```

Set `LOG_LEVEL` (default `INFO`, e.g. `DEBUG`) in `.env` to change verbosity. Every request
gets an ID — returned in the `X-Request-ID` response header and included in its log line, so a
failing response can be matched to its server-side traceback. Unhandled database, validation and
other errors are logged with that traceback and return a clean response (JSON for `/api`, an
HTML fragment for pages) instead of an unhandled traceback.

## Authentication

Authentication is a **placeholder**. The app uses HTTP Basic auth, but only the username is
looked up: the password is never checked, and users are created without one. This is
acceptable only because the app is single-user and reachable through a Tailscale tailnet.
Do not expose it to the public internet or to devices you do not trust. Real security would
mean hashing a password at user creation and verifying it in `meals.auth.get_current_user`.
