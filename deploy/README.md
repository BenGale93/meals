# Deployment

The app runs as a systemd service on the Pi (`galeb@192.168.1.135`), inside a checkout at
`/home/galeb/meals`, served by `uv run fastapi run src/main.py` on port `8000`. Releases are
deployed with `just deploy` (see below).

`meals.service` and `meals-next.service` in this directory are the version-controlled copies
of the live and candidate systemd units.

## Install / update the unit

This is the first-install path; `just deploy` reinstalls the unit automatically when it changes.

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

The unit also pins `TZ=Europe/London`, so `date.today()` and the roast timings use local time
regardless of the host default.

## Deploying a release

Run this **on the Pi**, in the checkout (it drives systemd and needs sudo):

```bash
DRY_RUN=1 just deploy   # show what would happen, change nothing
just deploy             # back up, pull, sync, restart, health-check
```

`just deploy` (via `scripts/deploy.sh`) refuses to start unless the tracked tree is clean and
`.env` exists, then:

1. writes a verified backup with the SQLite online backup API (per-table row counts printed);
2. `git pull --ff-only` and `uv sync --frozen`;
3. installs `deploy/meals.service` if it changed (`daemon-reload`);
4. restarts `meals` — the unit runs `alembic upgrade head` first — and polls
   `http://127.0.0.1:8000/health` for up to 30 seconds.

If the restart or health check fails it prints `systemctl status`, recent logs, and the
rollback steps, then exits non-zero. It never rolls back automatically: restore the backup
(see below) if the migration is not backward-compatible, then `git switch --detach
<previous commit>`, `uv sync --frozen`, and restart.

Run `just` (lint, type-check, tests) on the development machine before pushing; the Pi does
not run the test suite. For a risky schema change, prefer the side-by-side process below —
`just deploy` restarts in place.

## Side-by-side (blue/green) candidate

For a release whose code or migrations you want to exercise against real data before touching
the live service, run a candidate next to it (run this on the Pi, like `just deploy`). The
candidate is a second git worktree with its own `.env`, its **own copy** of the live database
and port `8001`; the live service keeps running on `8000` until you cut over.

```bash
just candidate                 # start/refresh the candidate at origin/master on :8001
just candidate start <ref>     # ... at another ref
# exercise the changed flows at http://ben-pi:8001 (over Tailscale)
just candidate promote         # back up the live DB, fast-forward, restart, health-check
just candidate stop            # free :8001, keep the checkout and DB copy
just candidate clean           # stop and remove the checkout, DB copy and unit
```

`just candidate` stops any previous candidate, creates or refreshes `/home/galeb/meals-next`
(a git worktree), copies the live database with the online backup API into
`<data dir>/candidate/meals.db`, writes a candidate `.env` pointing at that copy, runs
`uv sync --frozen --no-dev` (runtime dependencies only — the candidate does not need the
lint/test tooling), applies migrations to the copy, installs `deploy/meals-next.service`
(port `8001`, not enabled at boot) and waits for its `/health`. It refuses to start if the
candidate `DATABASE_URL` resolves to the live file, so exactly one process writes each SQLite
file.

`just candidate promote` takes a **fresh verified backup of the live database**, fast-forwards
the live checkout to the candidate commit, syncs, reinstalls `meals.service` if it changed,
restarts (the unit applies migrations to the **live** database) and waits for `/health`, then
stops the candidate. The candidate's database copy is deliberately not promoted: the live
database may have changed since it was copied, so the cutover migrates the live file after
backing it up. On failure the script prints the status, logs, previous commit, pre-cutover
backup path and rollback steps, and exits non-zero; the candidate stays up for comparison.

Keep the copy fresh (re-run `just candidate`) if validation takes a while, and remember the
candidate writes to the copy, never to live data. Work through **What to check on the
candidate** below before promoting.

## Migrations

The schema is owned by Alembic (`migrations/`); the app no longer creates tables at
start-up. Apply pending migrations before starting a new release:

```bash
just migrate                 # uv run alembic upgrade head, honouring .env
```

The existing database predates Alembic, so it is **stamped** once instead of upgraded
(`uv run alembic stamp head`). The baseline revision then counts as already applied and is
never replayed; running it against the unstamped database fails with
`table ingredients already exists`. Stamping is safe at any time (it only adds the
`alembic_version` table), but for a database that predates Alembic, stamp it **before**
enabling `ExecStartPre=` or running `alembic upgrade head`.

The live database was stamped when it was moved (2026-10-18). `meals.service` now runs
`alembic upgrade head` as an `ExecStartPre=` step, so `systemctl restart meals` applies any
pending migrations before the app starts; a failed migration aborts the start. The manual
`just migrate` command above is for local development or applying a migration without a
restart.

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

Routine releases use `just deploy` (above); it backs up and restarts in place. For a risky
schema change, use `just candidate` to validate a copy on `:8001` and `just candidate promote`
to cut over (see above). Nothing rolls back automatically — on failure the scripts print the
status, logs and steps, then exit non-zero.

To undo a release by hand:

```bash
sudo systemctl stop meals
git switch --detach <previous commit>
uv sync --frozen
sudo systemctl start meals
```

If the migration was not backward-compatible, also restore the database (see **Backups and
restore**) before starting.

### Safety rules

- **One writer per SQLite file.** Never point two processes (live and candidate) at the same
  database file. The candidate always uses its own copy, and `just candidate` refuses to start
  if its `DATABASE_URL` resolves to the live file.
- **The database path is explicit**, from the absolute `DATABASE_URL` in `.env`, never implied
  by the working directory — that is what lets two instances coexist.
- **Nothing irreversible happens on the live file.** Migrations are prepared and exercised on a
  copy; the live database is only touched at cutover, and only after a fresh verified backup. A
  backup is a point-in-time snapshot, so take a new one before every cutover rather than
  reusing an old one.
- **Every step is reversible**: before each cutover there is a fresh backup *and* the previous
  code commit on disk. Rollback is a restart, not a rebuild.
- **Freeze writes during the cutover window.** It is a single-user app: don't use it from the
  moment the cutover backup is taken until the new instance passes its health check.
- **One change per candidate.** Don't mix a dependency refresh, a tooling migration, and a
  schema change in one cutover; validate them separately so a failure is attributable.

### What to check on the candidate

Before promoting, exercise the changed flows at `http://ben-pi:8001` against real data:

- [ ] `/health` returns OK.
- [ ] The recipe list shows the expected number of recipes (compare with the counts
  `just candidate` printed for the copy).
- [ ] Open a recipe, edit it, save; confirm the change persists and re-reads.
- [ ] Planner: the current week renders and a planned day loads.
- [ ] Recipe summary counts look right (watch Bug 6: future meals are counted).
- [ ] The timings page saves (watch Bug 9: the `json-enc` extension is not loaded).
- [ ] Any flow this release touches, exercised against real data.
- [ ] No new errors in `journalctl -u meals-next`.

The data-safety checklist these rules come from is in [`../TODO.md`](../TODO.md) →
"Protect the live data".
