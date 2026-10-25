# Meals

A Python web app for managing the recipes you cook.

## Features

A recipe view for editing existing recipes, and adding new recipes.

A meal planning view for planning the weeks meals, seeing what you've eaten
recently/not so recently.

A Roast timer view, for planning the timings of roast dinners.

## Authentication

Authentication is a **placeholder**. The app uses HTTP Basic auth, but only the username is
looked up: the password is never checked, and users are created without one. This is
acceptable only because the app is single-user and reachable through a Tailscale tailnet.
Do not expose it to the public internet or to devices you do not trust. Real security would
mean hashing a password at user creation and verifying it in `meals.auth.get_current_user`.

## Development

```bash
just migrate      # create/update the schema with Alembic
just start        # dev server on http://127.0.0.1:8000
just              # lint, type-check and test (100% coverage enforced)
```

The app does not create tables itself; Alembic owns the schema (`migrations/`). After
changing `src/meals/database/models.py`, generate a migration with
`uv run alembic revision --autogenerate -m "describe the change"`.

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
(it is gitignored), and any `labels` in it are reported and skipped until label support lands
(TODO -> Features item 1). The database backup helper stays in `scripts/backup_db.py`
(`just backup`) because it works directly on SQLite without a running server.

## Deployment

The app runs as a systemd service on the Pi. Releases are deployed **on the Pi** with:

```bash
just deploy
```

That takes a verified backup, fast-forwards the checkout, syncs dependencies, restarts the
service (which applies Alembic migrations first), and waits for `/health`. For a risky release
(schema change), `just candidate` starts a side-by-side copy on `:8001` against a database
copy, and `just candidate promote` performs the cutover. See
[`deploy/README.md`](deploy/README.md) for the units, configuration, rollback, and restore
steps. Logs are at `journalctl -u meals -f`.

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
