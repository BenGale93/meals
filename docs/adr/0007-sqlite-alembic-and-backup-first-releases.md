# 0007: Run SQLite with an Alembic-managed schema and backup-first releases

- Status: Accepted
- Date: 2026-11-08

## Context

The app runs unattended on a Raspberry Pi and holds real recipe, planner, and timings data in
one SQLite file. The device is awkward to rebuild, and there is no CI or staging environment.
A schema mistake or a bad deploy can lose data that cannot be regenerated. The app is
single-user and low-traffic, so a database server and a multi-node deployment would add
operations without a clear benefit.

The live database predates Alembic and sits outside the checkout. It must survive a fresh
clone or `git clean`. The app also has to start against the right file or fail; creating an
empty schema at the wrong path would look like data loss.

Releases need two paths: a routine in-place deploy, and a way to exercise a risky schema change
against real data before touching the live service. The runbook is in `deploy/README.md`; this
ADR records the choices behind it.

## Decision

### SQLite and the database file

- Use SQLite through `aiosqlite`. The database is one file, located by the absolute
  `DATABASE_URL` in `.env`. In production it is `/home/galeb/meals-data/meals.db`, outside the
  checkout, so a clone or `git clean` cannot touch it.
- The default `sqlite+aiosqlite:///meals.db` is for local development only. The app reads
  `DATABASE_URL` through `meals.settings.database_url()`; systemd loads `.env` with
  `EnvironmentFile=`, and the `just` recipes pass `--env-file .env`. `.env` is gitignored, and
  `.env.example` documents the keys.
- The app enables SQLite foreign-key enforcement on every connection with
  `PRAGMA foreign_keys=ON`.
- One process writes each SQLite file. The live service and a candidate never share a database
  file.
- The root `conftest.py` sets `DATABASE_URL` to an in-memory database before importing
  `meals`, and each test builds its own throwaway SQLite file. The test suite cannot open the
  production file.

### Alembic ownership

- Alembic manages the schema. The app does not call `create_all` at start-up; a missing or
  wrong database fails instead of being created empty. Tests still use `metadata.create_all`
  to build their throwaway databases.
- `migrations/env.py` takes the URL from `meals.settings` and the metadata from
  `meals.database.models`. `alembic.ini` leaves `sqlalchemy.url` blank so migrations and the
  app cannot target different databases.
- Migrations use `render_as_batch=True` because SQLite cannot alter most things in place.
- The legacy database was stamped at the baseline revision `8b8ea410224a` on 2026-10-18. The
  baseline is already marked applied there and is not replayed. A fresh database applies the
  full chain with `alembic upgrade head` (`just migrate`). Before the stamp, the baseline was
  validated on a copy of the live database: `alembic check` reported no drift and the row
  counts were unchanged.
- The `meals` and `meals-next` systemd units run `alembic upgrade head` as `ExecStartPre=`, so
  a restart applies pending migrations before the app starts. A failed migration aborts the
  start. `just migrate` is for local development or a manual upgrade without a restart.
- Service start uses `uv run --frozen`; dependencies are synced during deploy, not resolved at
  start-up.

### Backups

- Back up with SQLite's online backup API through `scripts/backup_db.py` (`just backup`). The
  script opens the source read-only and calls `src.backup(dst)`. Do not `cp` a live database:
  a plain copy can catch a write in progress and can miss the `-wal`/`-shm` files. The script
  refuses to write a backup over its source file.
- Verify each backup by reopening it read-only and printing the row count of every table. The
  default destination is `<database dir>/backups/<stem>-<timestamp>.db`; `just backup <dir>`
  and `--to` choose another target, and `BACKUP_DIR` changes the default. Keep at least one
  copy off the Pi.
- Take a fresh backup before every deploy, migration, or cutover. An older backup is a
  point-in-time snapshot and does not include later edits.
- Restore with the service stopped, because SQLite allows one writer: copy the backup over the
  live file, remove stale `-wal`/`-shm` files, start the service, and check `/health` and
  `systemctl status`. The copy is a plain file copy only because the service is stopped.

### Releases

- Routine releases use `just deploy` (`scripts/deploy.sh`) on the Pi. It requires a clean
  tracked tree and `.env`, takes a verified backup with the current environment, fast-forwards
  with `git pull --ff-only`, runs `uv sync --frozen`, installs `deploy/meals.service` if it
  changed, restarts the service (which applies migrations), and polls `/health` for up to 30
  seconds.
- If the restart or health check fails, `just deploy` prints `systemctl status`, recent logs,
  and the rollback steps, then exits non-zero. It does not roll back automatically. Rollback
  returns the checkout to the previous commit, restores the pre-deploy backup if the migration
  is not backward-compatible, syncs dependencies, and starts the service.
- Risky schema changes use the side-by-side candidate: `just candidate` creates or refreshes a
  git worktree at `/home/galeb/meals-next`, copies the live database with the online backup
  API into `<data dir>/candidate/meals.db`, points the candidate `.env` at that copy, installs
  runtime dependencies only (`uv sync --frozen --no-dev`), migrates the copy, installs
  `deploy/meals-next.service` on port 8001, and waits for `/health`. The live service keeps
  running on 8000. The script refuses to start if the candidate URL resolves to the live file.
- Validate the changed flows against the candidate copy; the checklist is in
  `deploy/README.md`. `just candidate promote` takes a fresh verified backup of the live
  database, fast-forwards the live checkout to the candidate commit, syncs, reinstalls
  `meals.service` if it changed, restarts (applying migrations to the live database), waits
  for `/health`, and stops the candidate. The candidate's database copy is not promoted
  because the live file may have changed since it was copied; the cutover migrates the live
  file after the backup.
- If promote fails, the candidate stays up for comparison and the script prints status, logs,
  the previous commit, the backup path, and rollback steps. Rollback is the code rollback plus
  a database restore if the migration was not backward-compatible.
- Safety rules: one writer per file; an explicit absolute database path; no irreversible work
  on the live file; a fresh backup before each cutover; the previous commit on disk; writes
  frozen during cutover; one change per candidate.
- The Pi does not run the test suite. Run `just` (lint, type-check, tests) on the development
  machine before pushing. There is no CI.

## Consequences

- Operations stay file-based: there is no database server or network database to manage.
- SQLite allows one writer per file, so the live service and the candidate cannot share a
  database. The candidate needs a copy and a separate port.
- Schema changes are part of a restart. A bad migration can stop the service from starting,
  and rollback may need a database restore when the migration is not backward-compatible.
- The manual deploy and candidate process adds disk space and validation time, but lets a risky
  change run against real data before the live file is touched.
- Backups are snapshots. They must be refreshed before every change and copied off the Pi;
  row counts show that the copy is complete but are not a full integrity check.
- The live database is stamped at the Alembic baseline. New databases do not need that step;
  they apply the baseline and the later migrations.
- No CI and no test run on the Pi means the development `just` gate and the candidate checklist
  carry the release safety.
- There is no automatic rollback. An automatic restore could overwrite data written after the
  backup, so the scripts print the exact steps and leave the decision to the operator.

## Alternatives considered

- **PostgreSQL or another database server**: rejected because the app has one user and one
  writer; a server would add installation, backups, and connection management without solving
  a current problem.
- **Keep the database inside the checkout**: rejected because `git clean` or a fresh clone
  could delete it. The data lives at an explicit path outside the code.
- **Create tables with `create_all` at start-up**: rejected because it hides missing
  migrations, creates an empty schema when `DATABASE_URL` points at the wrong path, and cannot
  evolve existing data.
- **Recreate the database from migrations on each release**: rejected because the data is real
  and cannot be regenerated.
- **Back up with `cp`**: rejected because a live copy can be inconsistent and can miss the
  SQLite sidecar files. The online backup API gives one consistent snapshot.
- **Rely on an old backup**: rejected because each backup is a point-in-time snapshot. A fresh
  one is taken before every deploy, migration, or cutover.
- **Roll back automatically on failure**: rejected because a migration may already have
  changed the live file, and an automatic restore could discard writes made after the backup.
  The scripts print the status, logs, backup path, and steps instead.
- **Use the candidate database copy for the cutover**: rejected because the live database may
  have changed since the copy was taken. The live file is migrated in place after a fresh
  backup.
- **Run the candidate against the live database**: rejected because SQLite allows one writer,
  and validation would risk the live data.
- **Use the candidate for every release**: rejected because the copy, migration, second
  service, and validation pass are unnecessary for small changes. Routine releases use
  `just deploy`.
- **Run the tests on the Pi or add CI**: rejected for this single-user deployment; the Pi only
  has runtime dependencies, and the development `just` gate plus the candidate checklist cover
  the release. This can change if the deployment grows beyond one host and one user.
