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
| 3 | **Admin 2 + Data safety 4** — Alembic, baseline + `alembic stamp head` (done in code; live stamp at cutover) | Turns "delete the DB to change schema" into forward migrations. Baseline marks the existing tables as applied so the first migration never tries to recreate them. | Yes (for any schema change; recommended before all cutovers) |
| 4 | **Admin 4 + Data safety 1** — `just backup` / documented restore (done) | The cutover is only reversible if backup+restore is a one-liner you have actually run. | Yes |
| 5 | **Data safety 2** — move the DB out of the checkout | Stops `git clean`, re-clone, or `rsync --delete` from deleting the data. Folded into the first cutover (section 4). | Yes |
| 6 | **Admin 12** — this side-by-side process | The procedure itself. | Yes |
| 7 | **Admin 1** — systemd unit + `just deploy` | Reduces the manual cutover to `just deploy` and makes stop/start deterministic. Not needed for the very first manual cutover. | Recommended |
| 8 | **Bug 11** — enable SQLite foreign keys + pick WAL | WAL is kinder to the SD card and makes `.backup`/upgrades safer. Natural to set alongside Admin 3. | Recommended |
| 9 | **Admin 5** — logging + global exception handler | Makes candidate validation and rollback diagnosis much easier (journald logs rather than bare 500s). | Optional |
| 10 | **Admin 10 / Admin 11** — dependency refresh / mypy→pyrefly | These are *payloads* for a later candidate, not prerequisites. Do them on the candidate, never directly on live. | Optional |

**Progress (2026-10-18):** items 1, 2, 3 and 4 are **done** — `DATABASE_URL` is read from the
environment via `meals/settings.py` (with `.env.example`), the test suite is forced onto an
in-memory database by the root `conftest.py`, the `drop_all` line is gone, `just backup`
provides a verified, documented backup (restore steps in `deploy/README.md`), and Alembic now
owns the schema with a baseline validated against a copy of the Pi database. The systemd unit
is committed and installed (the unit half of item 7). Stamping the live database is safe as
soon as this release is deployed (section 4); the `ExecStartPre=` migration step and item 5,
plus the DB relocation itself, are still outstanding.

### 2.1 Admin 3 — make the DB path explicit (done)

`DATABASE_URL` is read from the environment by `meals.settings.database_url()`, defaulting to
the relative `sqlite+aiosqlite:///meals.db` so local development is unchanged. `.env.example`
documents the production value, and `deploy/meals.service` loads it via `EnvironmentFile=`:

```dotenv
# note the four slashes: scheme://<host>/<absolute-path>
DATABASE_URL=sqlite+aiosqlite:////home/galeb/meals-data/meals.db
```

The code half is done. The operational half (create the real `.env` on the Pi, move the
database, restart) happens in the first cutover, section 4 — **not** before, or the app would
start against an empty database at the new path.

### 2.2 Data safety 3 — test suite must not point at production (done)

Done, and insulated structurally rather than by convention: the root `conftest.py` sets
`DATABASE_URL=sqlite+aiosqlite:///:memory:` before any `meals` import, so the module-level
engine is never the real file. The commented `Base.metadata.drop_all` line has been deleted.
Verified by asserting the engine URL under pytest and confirming `meals.db` is never opened.

### 2.3 Admin 2 + Data safety 4 — Alembic baseline (done in code; live stamp at cutover)

Alembic is adopted with the async template (`migrations/`, `alembic.ini`). `migrations/env.py`
takes the URL from `meals.settings.database_url()` so migrations and the app can never
disagree about which database they mean, takes the metadata from `meals.database.models`, and
sets `render_as_batch=True` because SQLite cannot `ALTER` most things in place. The app no
longer calls `create_all` at start-up, so a mis-set `DATABASE_URL` fails loudly instead of
silently creating an empty schema.

The baseline revision (`migrations/versions/…_baseline.py`) was autogenerated from the models
and validated against a **copy of the Pi database** (the dev machine's `meals.db` has extra
label tables and is not representative — see TODO → Admin 8):

- `alembic stamp head` records the baseline without replaying it, and `alembic upgrade head`
  is then a no-op;
- `alembic check` reports `No new upgrade operations detected`, i.e. the baseline matches the
  real schema;
- row counts are unchanged by the stamp (it only adds `alembic_version`);
- a fresh `alembic upgrade head` produces the production schema exactly (checked with
  `.schema`), and `alembic downgrade base` removes it cleanly.

Running `alembic upgrade head` against an existing, **unstamped** database fails with
`sqlite3.OperationalError: table ingredients already exists`. That is why the live database
must be stamped before `ExecStartPre=alembic upgrade head` is enabled, and why both actions
belong to the first cutover (section 4) rather than to this change.

```bash
just migrate                       # alembic upgrade head, honouring .env
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic check               # verify models and migrations still agree
```

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

### Step 0 — confirm the launch mechanism

The live app is a systemd service: `meals.service` (enabled, running since 2026-10-01),
`ExecStart=uv run --frozen fastapi run src/main.py`, listening on `0.0.0.0:8000`, working
directory `/home/galeb/meals`. Stop/start is therefore `systemctl stop meals` /
`systemctl start meals` (or `restart`), and logs are `journalctl -u meals -f`.

The unit is now committed at `deploy/meals.service` and installed on the Pi (verified
2026-10-18), so the deployment is reproducible from source. Confirm the running unit matches
the repo before relying on it, and re-read its `EnvironmentFile` setting (the inert `.env`
hook that Admin item 3 activates):

```bash
systemctl cat meals            # show the unit and any drop-ins
systemctl show meals -p WorkingDirectory -p EnvironmentFiles -p User
```

### Step 1 — back up the live DB

```bash
just backup            # verified copy, honours .env; prints per-table row counts
```

Under the hood that is SQLite's online backup API writing
`sqlite3 <source> ".backup '<BACKUP>'"`; the difference is that `just backup` also reopens and
counts the copy so you know it is complete before you rely on it.

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
# Only if the copy predates Alembic (no alembic_version table). After the first
# cutover the live DB is stamped, so later copies already carry the version:
uv run alembic stamp head
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
(Data safety 2) and stamps it at the Alembic baseline. Because the live app only reads
`DATABASE_URL` after Admin 3 ships, the sequence is:

1. Complete prerequisites 1–4 in the dev checkout and merge to the release ref.
2. Take a fresh verified backup (`just backup`) and stop the service. On the Pi,
   `mkdir -p /home/galeb/meals-data` and **move** (not copy) the live database there:
   ```bash
   systemctl stop meals
   mv /home/galeb/meals/meals.db /home/galeb/meals-data/meals.db
   rm -f /home/galeb/meals/meals.db-wal /home/galeb/meals/meals.db-shm
   ```
3. **Stamp the moved database at the baseline** before any migration runs (skip if it was
   already stamped when this release was deployed — `alembic current` will show `head`):
   ```bash
   DATABASE_URL=sqlite+aiosqlite:////home/galeb/meals-data/meals.db \
     uv run alembic stamp head
   uv run alembic current          # expect <rev> (head)
   ```
   This only writes `alembic_version`; it does not replay the baseline. Confirm the row
   counts still match the backup. Skipping this makes the next `alembic upgrade head` fail
   with `table ingredients already exists`.
4. Create `/home/galeb/meals/.env` with the absolute
   `DATABASE_URL=sqlite+aiosqlite:////home/galeb/meals-data/meals.db`, then enable the
   `ExecStartPre=` line documented in `deploy/meals.service`, reinstall the unit, and start
   the release:
   ```bash
   sudo cp deploy/meals.service /etc/systemd/system/meals.service
   sudo systemctl daemon-reload
   sudo systemctl start meals
   ```
   The app no longer creates tables, so opening the wrong file would fail rather than create
   an empty DB — but verify the row counts immediately anyway (section 7). This is the one
   moment where a mis-set path looks exactly like data loss.
5. `/home/galeb/meals` is now code-only; the data lives in `/home/galeb/meals-data/`.

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
- `ExecStartPre=` runs `alembic upgrade head` (and, later, a verified backup), so a restart
  upgrades safely and a failed upgrade is restore-able. Enable it during the first cutover
  (section 4) only after the live database has been stamped.
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
