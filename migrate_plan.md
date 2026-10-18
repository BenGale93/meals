# Migration plan — side-by-side (blue/green) upgrades

Status: draft · 2026-10-18
Companion to `TODO.md`. This document turns the "run it on another port and migrate
smoothly" idea (TODO → Repo Admin item 12) into an ordered, executable plan, and lists the
`TODO.md` items that must land first.

**Goal.** Upgrade the Pi app without ever stopping the working one for long and without any
path that can lose data. The live app keeps serving from `/home/galeb/meals` on port `8000`;
a *candidate* is built next to it on port `8001` against a **copy** of the database, is
validated against real data over Tailscale, and only then is cut over in seconds. The
previous code checkout and a fresh database backup stay on disk for rollback.

**Scope.** The process below covers both code-only upgrades and schema upgrades. The
one-time prerequisites (section 2) are done once; the cutover procedure (section 3) is
repeated for every future release.

---

## 1. Principles (read before touching the Pi)

1. **One writer per SQLite file.** Never run the candidate and the live app against the same
   `meals.db`. The candidate always uses its own copy. SQLite allows one writer at a time;
   two writers means `database is locked` and possible corruption of your expectations.
2. **Nothing irreversible happens on the live file.** Migrations are prepared and tested on
   a copy; the live database is only ever touched during the brief cutover, and only after a
   fresh verified backup.
3. **Every step is reversible.** Before each cutover there is (a) a fresh DB backup and
   (b) the previous code checkout on disk. Rollback is a restart, not a rebuild.
4. **The database path is explicit, never implied by the working directory.** This is what
   makes two instances coexist cleanly and prevents "the app started with an empty DB".
5. **Freeze writes during the cutover window.** It is a single-user app; simply don't use it
   from the moment you take the cutover backup until the new instance is verified.
6. **One change per candidate.** Don't mix a dependency refresh, the type-checker migration,
   and a schema change in one cutover. Validate them separately so a failure is attributable.

---

## 2. Prerequisites (one-time, in the dev checkout)

These are the `TODO.md` items that must be completed before the first safe cutover. Order
matters — each depends on the one above it.

| # | TODO item | Why it is required | Blocking? |
| --- | --- | --- | --- |
| 1 | **Admin 3** — env-driven config (`DATABASE_URL`) | An absolute path from the environment is what lets the candidate and the live app use different DB files and lets the service be started from anywhere. | Yes |
| 2 | **Data safety 3** — tests must not touch production | `tests/test_app.py::test_lifespan_init_models` runs `create_all` against the relative `meals.db`; until fixed, running `just` in the Pi checkout opens the live DB. Also guard/remove the commented `drop_all` in `src/meals/database/session.py`. | Yes |
| 3 | **Admin 2 + Data safety 4** — Alembic, baseline + `alembic stamp head` | Turns "delete the DB to change schema" into forward migrations. Baseline marks the existing tables as applied so the first migration never tries to recreate them. | Yes (for any schema change; recommended before all cutovers) |
| 4 | **Admin 4 + Data safety 1** — `just backup` / documented restore | The cutover is only reversible if backup+restore is a one-liner you have actually run. | Yes |
| 5 | **Data safety 2** — move the DB out of the checkout | Stops `git clean`, re-clone, or `rsync --delete` from deleting the data. Folded into the first cutover (section 4). | Yes |
| 6 | **Admin 12** — this side-by-side process | The procedure itself. | Yes |
| 7 | **Admin 1** — systemd unit + `just deploy` | Reduces the manual cutover to `just deploy` and makes stop/start deterministic. Not needed for the very first manual cutover. | Recommended |
| 8 | **Bug 11** — enable SQLite foreign keys + pick WAL | WAL is kinder to the SD card and makes `.backup`/upgrades safer. Natural to set alongside Admin 3. | Recommended |
| 9 | **Admin 5** — logging + global exception handler | Makes candidate validation and rollback diagnosis much easier (journald logs rather than bare 500s). | Optional |
| 10 | **Admin 10 / Admin 11** — dependency refresh / mypy→pyrefly | These are *payloads* for a later candidate, not prerequisites. Do them on the candidate, never directly on live. | Optional |

### 2.1 Admin 3 — make the DB path explicit

Read `DATABASE_URL` from the environment with an absolute default, e.g. via a small settings
object, and commit a `.env.example`. On the Pi the service environment becomes:

```dotenv
# note the four slashes: scheme://<host>/<absolute-path>
DATABASE_URL=sqlite+aiosqlite:////home/galeb/meals-data/meals.db
TZ=Australia/Sydney
```

Until this ships to the live app, the current hardcoded relative
`sqlite+aiosqlite:///meals.db` means the candidate must be launched from a directory where
its copy happens to be named `meals.db` — workable but fragile, which is exactly why this
item comes first.

### 2.2 Data safety 3 — test suite must not point at production

Make the DB URL overridable in the test fixtures (point at `tmp_path`), or set
`DATABASE_URL` before importing the app. Delete or hard-guard the commented
`Base.metadata.drop_all` line so it can never be uncommented by accident. Confirm by running
`just` and checking the live `meals.db` mtime is unchanged.

### 2.3 Admin 2 + Data safety 4 — Alembic baseline

The app uses `aiosqlite`, so initialise Alembic with the async template:

```bash
uv run alembic init -t async migrations
uv run alembic revision --autogenerate -m "baseline"
```

For the **existing** database, mark it as already at the baseline instead of replaying it:

```bash
uv run alembic stamp head          # live / copied DB that already has the tables
```

For a brand-new database you use `uv run alembic upgrade head` instead. Verify the
autogenerated baseline matches the real schema **of a copy of the Pi database** (the dev
machine's `meals.db` contains extra label tables and is not representative — see TODO →
Admin 8).

### 2.4 Admin 4 + Data safety 1 — backup and restore

Add a `just backup` target and document the restore path. The backup must use SQLite's own
API, never `cp` on a live file:

```bash
sqlite3 /home/galeb/meals-data/meals.db \
  ".backup '/home/galeb/meals-backups/meals-$(date +%F-%H%M).db'"
```

Verify every backup by opening it read-only and counting rows (`users`, `recipes`,
`recipe_ingredients`, …), and keep at least one copy off the Pi.

---

## 3. The repeatable cutover procedure

Run this for every future release. `<BACKUP>` is a fresh timestamped backup path; `<COPY>` is
the candidate's own database file.

### Step 0 — the launch mechanism (already known)

The live app is a systemd service: `meals.service` (`/etc/systemd/system/meals.service`,
enabled, running since 2026-10-01), `ExecStart=uv run fastapi run src/main.py`, listening on
`0.0.0.0:8000`, working directory `/home/galeb/meals`. Stop/start is therefore
`systemctl stop meals` / `systemctl start meals` (or `restart`), and logs are
`journalctl -u meals -f`.

Capture the unit now so it can be committed and reviewed (Admin item 1), and so you know its
exact `WorkingDirectory`/`EnvironmentFile` before the first cutover:

```bash
systemctl cat meals            # show the unit and any drop-ins
systemctl show meals -p WorkingDirectory -p EnvironmentFiles -p User
```

Note the unit is **not** in the repo, so `/home/galeb/meals` is not a clean clone and the
release process is not reproducible from source yet.

### Step 1 — back up the live DB

```bash
sqlite3 /home/galeb/meals-data/meals.db ".backup '<BACKUP>'"
# verify it opens and has data
sqlite3 "file:<BACKUP>?mode=ro" "select count(*) from recipes;"
```

### Step 2 — build the candidate

Use a Git *worktree* or a plain copy — either way, never carry the live DB across:

```bash
git -C /home/galeb/meals worktree add /home/galeb/meals-next <release-ref>
# or: rsync -a --exclude .git --exclude '*.db' /home/galeb/meals/ /home/galeb/meals-next/

cd /home/galeb/meals-next
uv sync --frozen
cp '<BACKUP>' '<COPY>'     # candidate works on its own copy, never the live file
```

If you prefer a fresh directory, make sure `meals-next` does **not** contain a stale
`meals.db` other than `<COPY>`.

### Step 3 — apply migrations to the candidate copy

```bash
export DATABASE_URL=sqlite+aiosqlite:////home/galeb/meals-data-next/meals.db
uv run alembic stamp head     # existing schema → baseline is already applied
uv run alembic upgrade head   # apply anything newer than the baseline
```

Because this is a copy, a failed migration costs nothing — delete and re-copy.

### Step 4 — run the candidate on 8001 and validate

```bash
DATABASE_URL=sqlite+aiosqlite:////home/galeb/meals-data-next/meals.db \
  uv run fastapi run src/main.py --host 0.0.0.0 --port 8001
```

`fastapi run` listens on `0.0.0.0` with reload off; `PORT` may be set instead of `--port`.
Reach it over Tailscale at `http://<pi-tailscale-ip>:8001` and exercise the flows that
changed, plus the smoke checks in section 7. The temporary port is only reachable on the
tailnet.

### Step 5 — cut over

Stop using the live app (principle 5), then:

```bash
# 1. stop the live service
systemctl stop meals
# 2. if you want the prepared database, swap it in; otherwise migrate the live file now
#    (do this only with the old process stopped)
# 3. remove stale sidecars if you replaced the file
rm -f /home/galeb/meals-data/meals.db-wal /home/galeb/meals-data/meals.db-shm
# 4. start the new release
systemctl start meals
```

If nothing wrote to the live DB between step 1's backup and the cutover, the validated
candidate copy *is* current and step 5 is a file move plus restart — seconds of downtime. If
in doubt, re-copy the live DB after stopping and run `alembic upgrade head` on it directly
(downtime = migration time, which is why the prepared-copy path is preferred).

### Step 6 — verify

```bash
curl -fsS localhost:8000/health
journalctl -u meals -n 50
```

Then load the app over Tailscale and confirm real data is present (recipe counts, planned
days, timings).

### Step 7 — roll back (only if needed)

```bash
# stop the new instance
# restore the file:  cp '<BACKUP>' /home/galeb/meals-data/meals.db
# remove -wal/-shm, then start the previous checkout
```

Keep the previous release directory and the pre-cutover backup until you are satisfied.

### Step 8 — clean up

Stop the 8001 candidate, remove the worktree/candidate directory, and keep the backup per
your retention. Only now is the upgrade "done".

---

## 4. First cutover specifics (relocating the database)

The first cutover is special because it also moves the DB out of the checkout
(Data safety 2). Because the live app only reads `DATABASE_URL` after Admin 3 ships, the
sequence is:

1. Complete prerequisites 1–4 in the dev checkout and merge to the release ref.
2. On the Pi, `mkdir -p /home/galeb/meals-data` and **move** (not copy) the live database
   there while the app is stopped:
   ```bash
   systemctl stop meals            # or however it is launched
   mv /home/galeb/meals/meals.db /home/galeb/meals-data/meals.db
   rm -f /home/galeb/meals/meals.db-wal /home/galeb/meals.db-shm
   ```
3. Point the service's `EnvironmentFile` at `DATABASE_URL=sqlite+aiosqlite:////home/galeb/meals-data/meals.db`
   and start the new release. The app opening the wrong file would create an empty DB, so
   verify the row counts immediately (section 7) — this is the one moment where a mis-set
   path looks exactly like data loss.
4. `/home/galeb/meals` is now code-only; the data lives in `/home/galeb/meals-data/`.

After this, candidates and cutovers are routine and the DB is outside the reach of git and
deploy tooling.

---

## 5. Making it routine

Once one manual cutover has worked, fold it into tooling (Admin 1 + Admin 12 step 6):

- **Commit the existing unit** from `/etc/systemd/system/meals.service` into the repo
  (`deploy/meals.service`) and harden it: explicit `User=`/`Group=`, `EnvironmentFile=`
  (Admin 3), `Restart=on-failure`, `RestartSec`, and
  `ExecStart=uv run --frozen fastapi run src/main.py`.
- Consider pointing `WorkingDirectory`/`ExecStart` at a `current` symlink
  (`/home/galeb/meals-current` → `/home/galeb/releases/<date>`) so a cutover is a symlink
  swap plus `systemctl restart meals`, and rollback is swapping the link back.
- `ExecStartPre=` runs a verified backup and then `alembic upgrade head`, so a restart
  upgrades safely and a failed upgrade is restore-able.
- `just deploy` performs: fetch the release → `uv sync --frozen` → backup → migrate →
  `systemctl restart meals` → poll `/health` → fail loudly otherwise.
- Document the rollback procedure and `journalctl -u meals -f` in `README.md`.

---

## 6. Smoke checklist for the candidate (step 4 and step 6)

- [ ] `/health` returns OK.
- [ ] Recipe list shows the expected number of recipes (compare against the backup).
- [ ] Open a recipe, edit it, save; confirm the change persists and re-reads.
- [ ] Planner: current week renders; a planned day loads.
- [ ] Recipe summary counts match what you expect (watch TODO bug 6: future meals count).
- [ ] Timings page saves (TODO bug 9: the `json-enc` extension is not loaded).
- [ ] Any flow touched by this specific release, exercised against real data.
- [ ] No new errors in the service log.

---

## 7. Definition of done

- [ ] Live DB lives outside the checkout at an absolute, env-driven path.
- [ ] `just` no longer touches the live database.
- [ ] Alembic upgrades the schema forward; the existing DB is stamped at the baseline.
- [ ] `just backup` and a documented restore both work and have been tested on a copy.
- [ ] A candidate has been run on 8001 against a copy and validated with real data.
- [ ] A cutover has been performed and the previous release + backup are retained.
- [ ] The process is captured in `just deploy` / the systemd unit and `README.md`.
