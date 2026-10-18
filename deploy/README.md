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

The live database and `.env` were moved on 2026-10-18: the file is at
`/home/galeb/meals-data/meals.db` and `/home/galeb/meals/.env` sets the absolute
`DATABASE_URL` shown above. `/home/galeb/meals` is now code-only apart from the gitignored
`.env`. For a fresh install, create `.env` only once the database is actually at that path.

## Migrations

The schema is owned by Alembic (`migrations/`); the app no longer creates tables at
start-up. Apply pending migrations before starting a new release:

```bash
just migrate                 # uv run alembic upgrade head, honouring .env
```

The existing database predates Alembic, so it is **stamped** once instead of upgraded
(`uv run alembic stamp head`). The baseline revision then counts as already applied and is
never replayed; running it against the unstamped database fails with
`table ingredients already exists`. This is safe to do as soon as this release is deployed
(it only adds the `alembic_version` table) and is also folded into the first cutover in
[`../migrate_plan.md`](../migrate_plan.md) section 4.

Once the live database is stamped, enable the `ExecStartPre=` line documented in
`meals.service` so a restart applies pending migrations before the app starts.

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
