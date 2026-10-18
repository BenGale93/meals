# Deployment

The app runs as a systemd service on the Pi (`galeb@192.168.1.135`), inside a checkout at
`/home/galeb/meals`, served by `uv run fastapi run src/main.py` on port `8000`.

`meals.service` in this directory is the version-controlled copy of
`/etc/systemd/system/meals.service`.

## Install / update the unit

```bash
sudo cp deploy/meals.service /etc/systemd/system/meals.service
sudo systemctl daemon-reload
sudo systemctl enable --now meals
```

## Configuration

Configuration comes from an `EnvironmentFile` at `/home/galeb/meals/.env` (gitignored; see
`.env.example`). The important setting is an **absolute** `DATABASE_URL`, so the database
location is explicit rather than derived from the working directory:

```dotenv
DATABASE_URL=sqlite+aiosqlite:////home/galeb/meals-data/meals.db
```

Until the app reads `DATABASE_URL` from the environment (TODO → Admin item 3), the default
relative `sqlite+aiosqlite:///meals.db` is still used, so the database remains at
`/home/galeb/meals/meals.db`.

## Operations

```bash
systemctl status meals
journalctl -u meals -f          # logs
systemctl restart meals
```

## Backups and restore

Take a verified snapshot at any time — SQLite's online backup API is safe while the app is
running:

```bash
just backup                 # writes to <database dir>/backups
just backup /some/dir       # explicit destination
BACKUP_DIR=/some/dir just backup
```

`just backup` loads `.env` when present (so it targets the same database as the service) and
prints the row count of every table, which is how you confirm the copy is complete. Keep at
least one copy off the Pi.

Restore (SQLite allows one writer, so the service must be stopped):

```bash
sudo systemctl stop meals
cp <backup> <database path>
rm -f <database path>-wal <database path>-shm
sudo systemctl start meals
systemctl status meals --no-pager
```

## Upgrades and rollback

Use the side-by-side (blue/green) process in [`../migrate_plan.md`](../migrate_plan.md):
build and validate a candidate on port `8001` against a **copy** of the database, then cut
over with `systemctl restart meals`. Database safety rules (backup with SQLite's `.backup`,
never `cp` a live file, one writer per database file) are in
[`../TODO.md`](../TODO.md) → "Protect the live data".
