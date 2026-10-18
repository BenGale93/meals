# Meals

A Python web app for managing the recipes you cook.

## Features

A recipe view for editing existing recipes, and adding new recipes.

A meal planning view for planning the weeks meals, seeing what you've eaten
recently/not so recently.

A Roast timer view, for planning the timings of roast dinners.

## Development

```bash
just migrate      # create/update the schema with Alembic
just start        # dev server on http://127.0.0.1:8000
just              # lint, type-check and test (100% coverage enforced)
```

The app does not create tables itself; Alembic owns the schema (`migrations/`). After
changing `src/meals/database/models.py`, generate a migration with
`uv run alembic revision --autogenerate -m "describe the change"`.

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
