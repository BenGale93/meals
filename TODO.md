# TODO

Work items for the meals app, grouped into **Bugs**, **Repo Admin**,
**Architecture & Testing**, and **Features**. Each item is self-contained: it names the
relevant files and the expected outcome rather than prescribing every line.

## Deployment context

This app is self-hosted by a **single user** on a **Raspberry Pi**, reachable only over a
**Tailscale tailnet** (not the public internet). That changes priorities:

- **Multi-user** and **authenticated-impersonation** issues are *latent* — they cannot be
  triggered today, but they will bite if a second user is ever added or if anything on the
  tailnet is untrusted.
- Anything affecting the single user's **daily use**, **data durability**, or the ability
  to **upgrade the Pi in place** is more important than theoretical exposure.
- **Ops/deployment** is a first-class concern here: the app runs unattended on a device
  that is awkward to rebuild, so data-preserving upgrades and backups matter.
- **CI/CD is intentionally out of scope.** This is a solo project, so a hosted pipeline
  would be maintenance for no audience. "Deployment" in this document means making the Pi
  release repeatable, not automating pull requests — don't add a CI workflow.

Priorities: **P1** = affects the single user today; **P2** = latent, quality, or
operational hygiene; **P3** = optional / nice to have.

**Bugs and architecture outrank features.** Fix what is broken and pay down structural
debt before adding capability, so a Bug or Arch item outranks any Feature of the same
nominal priority; pick up Features only once no Bug/Arch item at that level remains.

Before finishing any item run `just` (lint + type_check + test). Coverage is enforced at
100% branch coverage, so every new branch needs a test. Follow the existing test layout
(`tests/api/`, `tests/web/`, `tests/conftest.py`) and update
`inline-snapshot` snapshots only after eyeballing the new output.

## Protect the live data (read this first)

The production database is a single SQLite file on the Pi, outside the checkout at
`galeb@192.168.1.135:/home/galeb/meals-data/meals.db`, and it holds real data. Treat the
following as prerequisites for Admin items 1–4: no migration, dependency upgrade, or deploy
change should be attempted until they are done.

**Status:** steps 1–5 are done. The live database now lives at
`/home/galeb/meals-data/meals.db` (moved 2026-10-18), `/home/galeb/meals/.env` points the app
and Alembic at it, and the live DB is stamped at the Alembic baseline. `just deploy` now takes
a verified backup before every restart.
Note that each backup is a point-in-time snapshot and will not include later edits to the
app's data, so **take a fresh one before every migration or deploy** (`just deploy` does this
automatically); do not treat an old backup as permanently done.

- [x] **1. Back up using SQLite's backup API — not `cp`.** A backup has been taken and copies
  are held on the Pi and locally. For future refreshes, use `just backup` (see Admin item 4):
  it wraps `sqlite3 ... ".backup ..."`, so it never `cp`s a live file (which can capture a
  torn database and misses the `-wal`/`-shm` sidecars), and it reopens the copy and prints
  per-table row counts so you can confirm it is complete. Keep at least one copy off the Pi.
- [x] **2. Move the database out of the checkout.** Done 2026-10-18: the live DB is at
  `/home/galeb/meals-data/meals.db`, `/home/galeb/meals/.env` sets
  `DATABASE_URL=sqlite+aiosqlite:////home/galeb/meals-data/meals.db`, and the service was
  restarted and verified (`/health` OK, row counts unchanged, `alembic current` = head,
  `alembic check` clean). `just backup` follows `.env`, so it now reads and writes outside the
  checkout. `/home/galeb/meals` is code-only apart from the gitignored `.env`. A `git clean
  -fdx` or fresh clone can no longer touch the data.
- [x] **3. Never let the test suite or dev tooling point at production.** Done:
  `DATABASE_URL` is now read from the environment via `meals.settings.database_url()` (root
  `conftest.py` forces `sqlite+aiosqlite:///:memory:` before any `meals` import, so the suite
  can no longer open a real `meals.db`), and the commented-out `Base.metadata.drop_all` line
  in `src/meals/database/session.py` has been deleted.
- [x] **4. Adopt Alembic against the real schema, don't recreate it.** Done: Alembic owns the
  schema (`migrations/`, `alembic.ini`), `migrations/env.py` takes the URL from
  `meals.settings` and the metadata from `meals.database.models` with `render_as_batch`, and
  the app no longer calls `create_all` at start-up (so a mis-set path fails loudly instead of
  creating an empty schema). The baseline was generated from the models and validated on a
  **copy** of the live DB: `alembic stamp head` marks it applied, `upgrade head` is then a
  no-op, `alembic check` reports no drift, and row counts are unchanged. The live database
  was stamped at `8b8ea410224a (head)` on 2026-10-18 when it was moved (step 2), and
  `ExecStartPre=alembic upgrade head` is now enabled. The stamp had to happen first: the
  baseline would otherwise fail with `table ingredients already exists`.
- [x] **5. Make the deploy flow backup-then-migrate, and rollback a file swap.** `just deploy`
  takes a verified backup, then pulls, syncs, and restarts (the unit's `ExecStartPre` applies
  migrations); on failure it prints the restore path. The documented rollback is: stop the
  service, restore the `.db` file (and remove any stale `-wal`/`-shm`), start the service,
  verify — with `git switch --detach <previous commit>` for the code half. See Admin item 12
  for the side-by-side version.

## Priorities at a glance

| Item | Priority |
| --- | --- |
| Bug 2 — rename recipe onto existing name (500) | P1 |
| Bug 3 — duplicate ingredient in one request (500) | P1 |
| Bug 6 — summary counts future meals | P1 |
| Bug 7 — blank ingredient on edit shows raw error | P1 |
| Bug 8 — page shells public, fragments 401 | P1 |
| Bug 10 — web recipe pages 500 on missing recipe | P1 |
| Admin 1 — better deployment to the Pi | P1 |
| Admin 2 — data-preserving migrations (Alembic) | P1 |
| Admin 3 — env-driven config / DB path | P1 |
| Admin 4 — backups / export of `meals.db` | P1 |
| Admin 10 — migrate mypy → pyrefly | P1 |
| Admin 11 — side-by-side (blue/green) upgrades | P1 |
| Bug 9 — `hx-ext="json-enc"` never loaded | P2 |
| Bug 1 — global uniqueness constraints | P2 (latent) |
| Bug 4 — cross-user planned-day auth hole | P2 (latent) |
| Bug 5 — passwords never checked | P2 (hardening) |
| Bug 11 — SQLite foreign keys not enforced | P2 |
| Bug 12 — brittle ingredient parsing | P2 |
| Admin 5 — logging / exception handler | P2 |
| Admin 6 — seed/CLI scripts | P2 |
| Admin 7 — `feat/labels` branch triage | P2 |
| Admin 8 — tooling/documentation tidy | P3 |
| Admin 9 — refresh dependencies | P2 |
| Arch 1 — share logic between API and web | P1 |
| Arch 2 — eager-loading assumptions in response models | P2 |
| Arch 3 — split the `schemas.py` grab-bag | P2 |
| Arch 4 — fragile `PageRegistry` import side effects | P3 |
| Arch 5 — import-linter contract gaps | P3 |
| Arch 6 — test fixtures mutate the global app | P2 |
| Arch 7 — test DB session ≠ production transactions | P2 |
| Arch 8 — brittle full-page snapshots | P2 |
| Arch 9 — coverage pragmas hide gaps | P2 |
| Arch 10 — split large test modules by domain | P3 |
| Features 1–9 | see each item |

---

## Bugs

### 1. (Latent) Uniqueness constraints are global, not per-user — P2 (done)

**Fixed:** `recipes.name` and `planned_days.day` no longer use `unique=True`; both tables now
have a composite `UniqueConstraint("user_pk", "name")` / `("user_pk", "day")`. Migration
`50a4ce8e8245` drops the old single-column constraints and adds the composite ones in batch
mode (verified upgrade, downgrade and `alembic check` on a fresh database). Tests prove two
users can reuse a recipe name and plan the same day, while the application-level 409s are
unchanged.

`recipes.name` and `planned_days.day` are declared `unique=True` on the column
(`src/meals/database/models.py`), but every repository lookup is scoped to the user
(`filter_by(name=..., user_pk=...)`, `filter_by(day=..., user_pk=...)`). With a single
user this is harmless — in fact the global constraints are the only thing enforcing
uniqueness today. It only breaks when a second user is added, at which point a second
user's create passes the application-level check and then hits the DB constraint,
producing an unhandled `IntegrityError` (HTTP 500).

Reproduction (confirmed): user one creates "Carrot Surprise", user two creates the same
recipe name → `sqlite3.IntegrityError: UNIQUE constraint failed: recipes.name`; likewise
two users planning the same date → `UNIQUE constraint failed: planned_days.day`.

Only worth doing if multi-user is on the roadmap. Fix by replacing the single-column
uniqueness with composite `UniqueConstraint("user_pk", "name")` and
`UniqueConstraint("user_pk", "day")`, keeping the 409 responses in
`src/meals/api/v1/routes.py`, and adding a test proving two users can independently reuse
a name and plan the same day. If multi-user is not planned, consider closing this item
with a note.

### 2. Renaming a recipe onto an existing name raises a 500 — P1 (done)

**Fixed:** `RecipeRepository.update` now raises `RecipeAlreadyExistsError` when the target name
belongs to a different recipe, and `PUT /api/v1/recipes` maps that to a 409.

`RecipeRepository.update` (`src/meals/database/repository.py`) never checks for a name
collision, even though `create` does. Updating a recipe so its `name` matches another of
the user's recipes returns an unhandled `IntegrityError` instead of a 409.

Reproduction (confirmed): create two recipes, rename one to the other's name →
`UNIQUE constraint failed: recipes.name`.

This affects the single user directly (e.g. tidying up duplicates). Return
`RecipeAlreadyExistsError` (the route already maps it to 409) or otherwise handle it, and
add an API test.

### 3. Duplicate ingredient name within one request raises a 500 — P1 (done)

**Fixed:** `CreateRecipeRequest`/`UpdateRecipeRequest` now reject repeated ingredient names during
validation (422), instead of letting `create` queue a duplicate `StoredIngredient` and flush an
`IntegrityError` (or letting `update` silently pick one quantity).

In `RecipeRepository.create`, the ingredient lookup runs inside `session.no_autoflush`, so
a `StoredIngredient` added earlier in the same loop is not visible to the next lookup and
a second row with the same `name` is queued. The flush then violates `ingredients.name`
uniqueness.

Reproduction (confirmed): `POST /api/v1/recipes` with ingredients
`["Carrot 1 unit", "Carrot 2 units"]` → `UNIQUE constraint failed: ingredients.name`.
The same pattern exists in `RecipeRepository.update` when adding several new ingredients.

This happens easily when a user lists the same ingredient twice. Decide the intended
behaviour (probably sum quantities or reject with a clear 422) and cover it with a test.
Rejecting duplicate names in `CreateRecipeRequest`/`UpdateRecipeRequest` validation is the
simplest fix.

### 4. (Latent) Cross-user authorization hole in `POST /api/v1/planned_day` — P2 (done)

**Fixed:** `PlanService.plan` looks the recipe up scoped to the requesting user and raises
`RecipeDoesNotExistError`, which the API maps to 404. `PlanRepository.summarise` also scopes
its outer join to `StoredPlannedDay.user_pk`, so a pre-existing plan stored by another user
cannot inflate the owner's counts. Tests cover the rejected cross-user plan and the summary.

`PlanRepository.update` blindly sets `planned.recipe_pk = planned_day.recipe.pk` without
verifying the recipe belongs to the requesting user. Any authenticated user (i.e. anything
on the tailnet) can plan a recipe that belongs to someone else by supplying its `pk`.

Reproduction (confirmed): user two posts `{"day": "2025-01-01", "recipe": {"pk": 1, ...}}`
using user one's recipe pk → 201, and the plan is stored.

Only relevant once there is more than one user. Verify recipe ownership in the
repository/route (404/403 on mismatch) and also scope `PlanRepository.summarise` by
`StoredPlannedDay.user_pk` (see bug 6).

### 5. Passwords are never checked (auth is username-only) — P2 (done)

**Fixed (documentation only):** `README.md` now has an Authentication section stating that the
password is a placeholder and only the username is checked, and `get_current_user`'s docstring
says the same. No hashing or session flow was added for this single-user, Tailscale-only app.

`src/meals/auth.py` only looks the user up by `credentials.username` and ignores
`credentials.password`; `CreateUserRequest` has no password field and `auth_headers()`
hardcodes the password `"test"`. Any client on the tailnet can authenticate as the
account with an arbitrary password.

Because the app is single-user and only reachable over Tailscale, this is **not** an
urgent exposure — Tailscale already provides transport encryption and access control, and
no password ever needs to leave the tailnet. Treat it as hardening / future-proofing:

- At minimum, document that auth is a placeholder in `README.md` so it isn't mistaken for
  real security.
- If you add a password at all, hash it (Argon2/bcrypt) and verify it in
  `get_current_user`; never return the hash in `UserResponse`.
- A full signup/login/logout flow is likely overkill for a single-user Tailscale app;
  a long-lived signed session cookie (so the browser stops re-prompting for Basic auth)
  is probably the sweet spot.

### 6. Recipe summary counts future meals — P1 (done)

**Fixed:** `PlanRepository.summarise` only counts planned days on or before `date.today()` (the
bound lives in the outer-join `ON` clause so unplanned recipes still appear with count 0).

`PlanRepository.summarise` counts every linked `planned_days` row and takes `max(day)`
with no upper date bound, so meals planned for next week are reported as "eaten" and
`last_eaten` can be in the future. Reproduction (confirmed): travel to 2025-01-01, plan a
meal on 2025-01-08, `GET /api/v1/planned_day/summary/` reports
`count: 1, last_eaten: 2025-01-08`.

This is a genuine single-user annoyance: planning the week ahead makes the "Recipe
Summary" table claim you've already eaten those meals. Filter to `day <= today` (the
cross-user scoping from bug 4 is moot here). The existing `test_summarise` in
`tests/test_api.py` deliberately plans a future date and expects it to count, so that test
needs updating as part of the fix.

### 7. Editing a recipe with a blank ingredient shows a raw validation dump — P1 (done)

**Fixed:** `update_recipe` filters out blank ingredient strings (like `new_recipe`) and reuses the
shared `format_new_recipe_error` formatting, so clearing the last ingredient works and errors are
readable rather than raw pydantic output.

`update_recipe` in `src/meals/web/index.py` passes the submitted ingredient strings
straight into `UpdateRecipeRequest`, while `new_recipe` in `src/meals/web/new.py` filters
out empty strings first. Clearing the last ingredient in the edit form therefore fails
validation and returns `update_recipe_error`, which dumps the raw pydantic error
("1 validation error for UpdateRecipeRequest ...").

Reproduction (confirmed): `POST /update_recipe/{pk}` with `ingredients=[""]` returns the
raw dump. This also means you can't remove the last ingredient via the edit form.

Filter blank entries like the new-recipe route does, and reuse the friendly
`format_new_recipe_error` formatting so the web error component is consistently readable.
Add tests for clearing ingredients.

### 8. Page shells are public but their content is authenticated — P1 (done)

**Fixed:** the `index`, `new`, `plan`, and `timings` page routes now take a `CurrentUser`
dependency, so an unauthenticated page load returns 401 (with `WWW-Authenticate: Basic`) instead
of rendering a shell whose HTMX fragments fail over XHR.

`index`, `new`, `plan`, and `timings` page handlers in `src/meals/web/*.py` take no
`CurrentUser` dependency, so `GET /`, `/new.html`, `/plan.html`, `/timings.html` render
without auth. The HTMX fragments they load (`/recipe_list`, `/recipes`, `/weeks_plan`,
`/summary`, `/timings`) do require auth, so on first load the browser gets a page whose
content fails with 401 over XHR (which does not reliably trigger a usable Basic-auth
prompt).

For a single user this is a real "why is the page empty?" annoyance every time the session
resets. Either require `CurrentUser` on the page routes too, or add a simple login page
and redirect unauthenticated users to it (ties into bug 5).

### 9. `hx-ext="json-enc"` is used but the extension is never loaded — P2 (done)

**Fixed:** dropped `hx_ext="json-enc"` from the Save Timing button. HTMX now uses its default
form encoding, which is exactly what the `Form()`-based `PATCH /timings` route reads. A test
asserts the markup no longer references the unloaded extension and still sends `hx-vals`.

`save_timing()` in `src/meals/web/timings.py` sets `hx_ext="json-enc"`, but no `json-enc`
script is included in the page layout (`page()` in `src/meals/web/core.py`). HTMX
currently ignores the unknown extension and falls back to form encoding, which is why the
`Form()`-based route works. Confirm the timings "Save" button actually persists edits in a
browser, then either load the extension and switch the route to a JSON body, or drop the
attribute so the markup matches reality.

### 10. Web recipe pages 500 on a missing recipe instead of 404 — P1 (done)

**Fixed:** `get_recipe` and `edit_recipe` raise a 404 when `repo.get` returns `None`, matching the
JSON API, instead of passing `None` into `RecipeResponse.model_validate`.

`get_recipe` and `edit_recipe` in `src/meals/web/index.py` call `repo.get(pk, user.pk)`
and pass the result (which may be `None`) straight into
`RecipeResponse.model_validate(...)`, which raises a `ValidationError` → HTTP 500. The JSON
API routes already handle this case with a 404. Reproduction (confirmed): `GET /recipe/9999`
and `GET /recipe/9999/edit` raise; they should return a 404 (or a small "recipe not found"
fragment). `update_recipe` already handles the missing case via `RecipeDoesNotExistError`,
so use that as the pattern.

### 11. SQLite foreign keys are not enforced — P2 (done)

**Fixed:** `create_async_db_engine` registers a connect listener that runs
`PRAGMA foreign_keys=ON`; tests use the same factory, so the suite exercises it.
`planned_days.recipe_pk` is now `ON DELETE CASCADE` with `passive_deletes` on
`StoredRecipe.planned`, so deleting a recipe removes its plans (migration `0cba625154a2`).
Tests assert the pragma, reject an orphan join row, and verify the cascade.

`PRAGMA foreign_keys` defaults to OFF in SQLite and nothing enables it
(`src/meals/database/session.py`). Reproduction (confirmed): inserting a
`RecipeIngredient(recipe_pk=999, ingredient_pk=999)` with no matching parents flushes
successfully, and `PRAGMA foreign_keys` reports `0`. So the `ForeignKey`/`ondelete="CASCADE"`
declarations in `src/meals/database/models.py` are decorative outside the ORM's own
cascades, and bugs or manual SQL can leave orphaned rows. It also means
`StoredPlannedDay.recipe_pk` (which has no `ondelete` and no relationship cascade) will
either block or orphan deletes once recipe deletion lands (Features item 5). Enable it via
a `connect`-event listener (`PRAGMA foreign_keys=ON`), decide the delete behaviour for
planned days, and test the cascade. Latent now, but becomes P1 the moment recipe deletion
is implemented.

### 12. Ingredient parsing is brittle — P2 (done)

**Fixed:** the parser now accepts name-first or quantity-first forms with integer, decimal or
fractional quantities and a single-word unit: `Flour 2 cups`, `500g beef`, `2 tins tomatoes`,
`1/2 cup sugar`, `1.5 kg beef`. Unitless input is still rejected, and the error message lists
accepted examples. Tests cover both accepted and rejected forms.

`INGREDIENT_REGEX` in `src/meals/schemas.py` only accepts `name quantity unit`, in that
order, with a space-separated numeric quantity. Reproduction (confirmed) — these common
inputs are all rejected: `"500g beef"`, `"2 tins tomatoes"`, `"1/2 cup sugar"`,
`"1.5 kg beef"`, and anything with no quantity (`"Salt"`). The new-recipe placeholder
("Flour 2 cups") advertises the one supported shape, so this will be hit in normal use.
Decide the intended grammar (quantity-first, fractions, unitless staples), improve the
error message to show examples of accepted forms, and add tests for the accepted and
rejected cases.

---

## Repo Admin

### 1. A better way to deploy to the Pi — P1 (done)

Deployment already runs under systemd, and the unit is now **in the repository**. A hardened
copy of `/etc/systemd/system/meals.service` is committed at `deploy/meals.service` (installed
and verified on the Pi 2026-10-18): `ExecStart` is the production command
`uv run --frozen fastapi run src/main.py`, `WorkingDirectory` is the checkout
`/home/galeb/meals`, and it listens on `0.0.0.0:8000` (LAN clients at `192.168.1.x` reach it
in the logs). The release is now one command: `just deploy` on the Pi (via
`scripts/deploy.sh`) takes a verified backup, fast-forwards the checkout, runs
`uv sync --frozen`, reinstalls the unit if it changed, restarts the service (its
`ExecStartPre=` applies migrations), and polls `/health`; the notes are in `README.md` and
`deploy/README.md`. (`just start` remains the auto-reload development server.) The goal was
to make a release one command that survives reboots and upgrades without data loss.

For a single self-hosted service on one Pi, **systemd remains the least machinery and the
recommended path** — it is already the chosen path, so this is consolidation rather than a
rewrite:

- Keep the production command (`fastapi run src/main.py`) with no `--reload`. It currently
  binds `0.0.0.0` and LAN clients use it, so only narrow that to the Tailscale address if you
  actually want LAN access gone; TLS is unnecessary inside Tailscale.
- **The unit is version-controlled** (done). `deploy/meals.service` (with install notes in
  `deploy/README.md`) has explicit `User=`/`Group=`,
  `EnvironmentFile=-/home/galeb/meals/.env`, `Environment=PYTHONUNBUFFERED=1`,
  `Environment=TZ=Europe/London`, `ExecStart=.../uv run --frozen fastapi run src/main.py`,
  `Restart=on-failure`, `RestartSec=5`, `SyslogIdentifier=meals`, `NoNewPrivileges=true`,
  `PrivateTmp=true`.
  Re-install after any change with `just deploy` (it compares the unit and does
  `daemon-reload` + `restart`), or manually with `sudo cp ...` and a restart. Do **not**
  rely on the working directory for the database path (see Admin item 3).
- Run migrations as an `ExecStartPre=` step (done: `alembic upgrade head`), and take a verified
  backup before a restart as part of `just deploy` (done), so a restart upgrades the schema
  safely and a failed upgrade can be rolled back by restoring the file.
- **`just deploy` is implemented** (`scripts/deploy.sh`): verified backup → `git pull
  --ff-only` → `uv sync --frozen` → reinstall the unit if it changed → `systemctl restart`
  (migrations run in `ExecStartPre`) → poll `/health`; a failure prints status, logs, and the
  rollback steps and exits non-zero. It refuses a dirty tracked tree, requires `.env`, and
  never rolls back automatically. `DRY_RUN=1 just deploy` shows the plan.
- Logs go to journald automatically; `journalctl -u meals -f` is documented in `README.md`
  and `deploy/README.md`. (Done.)

A `Dockerfile` + compose file is a reasonable alternative if you want process isolation,
but it adds image build/pull tooling to a job that is otherwise a `git pull` and a
restart. Whichever you choose, document it in `README.md` together with the rollback
procedure and a note that `scripts/plan_meal.py` expects a running server.

Pi-specific details to get right at the same time:

- Set `TZ` in the service environment so `date.today()` and the roast timings reflect local
  time rather than UTC. (Done: `Environment=TZ=Europe/London` in the unit.)
- Confirm prebuilt wheels exist for the pinned dependencies on the Pi's architecture
  (`pydantic-core`, `greenlet`, and uvicorn's `uvloop`/`httptools`). Raspberry Pi OS 64-bit
  (`aarch64`) is well supported; 32-bit (`armv7l`) often is not — check before an upgrade.
- Decide on the SQLite journal mode (WAL is kinder to an SD card and to the backup/upgrade
  flow) when foreign keys are enabled (bug 11).

### 2. Data-preserving migrations (Alembic) — P1 (done)

`init_models`/`create_all` is gone; Alembic now owns the schema. `uv add alembic` plus
`alembic init -t async migrations` set up `alembic.ini` and `migrations/`, with `env.py`
reading the URL from `meals.settings.database_url()` (so migrations and the app can never
disagree), the metadata from `meals.database.models`, and `render_as_batch=True` (SQLite
cannot `ALTER` most things in place).

The baseline revision (`migrations/versions/…_baseline.py`) was autogenerated from the
models and validated against a copy of the Pi database: `alembic stamp head` records it
without replaying it, `alembic check` reports no drift, and a fresh `alembic upgrade head`
produces exactly the production schema (verified by comparing `.schema` dumps). Tests still
build their schema directly from the metadata, so they never touch the real file.

`just migrate` applies pending migrations (honouring `.env`). The live database was stamped at
the baseline on 2026-10-18 and `.env` points at it (see **Protect the live data** steps 2 and
4). `deploy/meals.service` now runs `alembic upgrade head` as an `ExecStartPre=` step, so a
restart migrates before the app starts and a failed migration aborts the start. The remaining
deploy work (a verified backup before restart, and `just deploy`) is Admin item 1 / data-safety
step 5.

This is the prerequisite for the labels work (Features item 1), which adds several tables,
and it is the single most valuable item for data durability.

### 3. Make configuration env-driven — P1 (done)

`DATABASE_URL` was hardcoded to the relative path `sqlite+aiosqlite:///meals.db`, so under a
systemd unit the working directory silently decided which file was opened. Now done: a small
`meals/settings.py` exposes `database_url()`, which reads `DATABASE_URL` from the environment
and defaults to the relative `sqlite+aiosqlite:///meals.db` (so local development is
unchanged). `meals.database.session` builds its engine from it, `.env.example` documents the
setting, and `deploy/meals.service` loads it via `EnvironmentFile=`. Tests are insulated (see
**Protect the live data** step 3).

The operational half is also done (2026-10-18): `/home/galeb/meals/.env` sets the absolute
`DATABASE_URL`, the database was moved to `/home/galeb/meals-data/meals.db`, and the service
was restarted and verified (see **Protect the live data** step 2).

### 4. Backups / export of `meals.db` — P1 (done)

The only copy of your data is a single SQLite file on the Pi, so a simple, documented backup
path now exists: `just backup` runs `scripts/backup_db.py`, which uses SQLite's online backup
API (safe while the app runs), honours `DATABASE_URL`/`.env` and `BACKUP_DIR`, and prints the
row count of every table so the copy is verified rather than assumed. Restore is documented
in `deploy/README.md` (stop the service, copy the file, remove `-wal`/`-shm`, start).

Still worth considering: a scheduled off-Pi copy (a `meals-backup.timer` systemd unit, or a
`scp`/`rsync` to another machine on the tailnet), and the JSON/YAML export in Features
item 6.

### 5. Add logging and a global exception handler — P2 (done)

**Fixed:** logging is configured once in `meals/logging_config.py`: one JSON object per line on
stdout (so journald captures it), a `RequestIdFilter` that stamps every record with the current
request ID, and a `LOG_LEVEL` setting (default `INFO`). `meals/middleware.py` gives every HTTP
request an ID (reusing a caller-supplied `X-Request-ID`), returns it in the response header, and
logs method, path, status and duration. `meals/error_handlers.py` handles SQLAlchemy errors,
pydantic `ValidationError`, FastAPI's `ResponseValidationError`, and a catch-all: each logs the
traceback with the request ID and returns a clean response — JSON with a `request_id` field for
`/api` routes, a small HTML fragment for pages. The `# TODO: add logging here` in
`src/meals/web/new.py` now logs the unexpected case. Tests live in `tests/test_logging.py`.

There is no `@app.exception_handler` and no logging configuration; unhandled
`IntegrityError`s surface as bare 500s, and `src/meals/web/new.py` has a
`# TODO: add logging here`. On a headless Pi this makes debugging hard. Add structured
logging that goes to journald (or the container log), a handler for database/validation
errors that returns a clean response, and request IDs.

### 6. Fix the seed/CLI scripts — P2 (done)

**Fixed:** the two HTTP helpers moved into the package as `meals.cli.populate_db` and
`meals.cli.plan_meal`, are exposed as the `meals-seed` and `meals-plan` console scripts
(`[project.scripts]`), and `typer`/`rich` are now direct dependencies instead of arriving
transitively through `fastapi[standard]`. `meals-seed` now seeds both files: it creates the
user if needed, posts the recipes (skipping existing ones so re-running is safe), and sends
the roast timings via `PATCH /timings` (an upsert). `timings.yaml` uses the schema's
`finish_time`/`description` keys. `recipes.yaml` labels are now validated and reported as
skipped, rather than silently dropped, until Features item 1 adds label storage. Tests in
`tests/test_cli.py` drive both commands (and the seeding path against the ASGI app), keeping
the new package modules at 100% coverage. The `pydantic-yaml` warning noted below is already
gone with the current pydantic/FastAPI versions (see Admin item 9), so no change was needed
there. `scripts/backup_db.py` stays outside the package because it works on the SQLite file
itself and must run without a server.

`scripts/populate_db.py` only seeds recipes, silently drops the `labels` present in
`recipes.yaml` (the current `CreateRecipes`/`CreateRecipeRequest` schemas have no `labels`
field), and never loads `timings.yaml` (whose `end`/`step` keys don't match
`TimingsCreate`'s `finish_time`/`description`). `typer`, `rich`, and `httpx` are used by
the scripts but pulled in only transitively via `fastapi[standard]`, and
`[project.scripts]` in `pyproject.toml` is empty. Give the scripts explicit
dependencies/entry points, make `populate_db.py` also seed timings (reconciling the YAML
keys), and seed labels once they exist. Also note `pydantic-yaml` emits a Pydantic V1
warning on Python 3.14 — check whether an upgrade or alternative is needed.

### 7. Triage the `feat/labels` branch — P2

`origin/feat/labels` (branched from `07102bd`) contains an implemented-but-unmerged
labels backend: new `Category`/`SubCategory`/`StoredRecipeLabel` models, label schemas,
repository support, and a large restructure of the API tests into `tests/api_tests/`.
The tip commit is literally "WIP". Rebase it on `master` (it is one formatting commit
behind), verify `just` passes, review the schema design (e.g. `SubCategory.name` is not
unique within a category, `Category.sub_categories` is typed as a single item), and either
finish/merge it or close it with a note. Do not duplicate this work in Features item 1.
Also clean up the stale `tests/api_tests/` directory left on disk from that branch (only a
`__pycache__` remains) so it can't confuse a later checkout. The branch is genuinely
unmerged and not deployed (the Pi database has no labels tables); note that the dev
checkout's own `meals.db` *does* contain label tables from an earlier experiment, so it is
not a valid stand-in for the production schema.

### 8. Tidy tooling and documentation — P3 (done)

**Fixed:** the stale `filterwarnings` comment in `pyproject.toml` now says "except from our
own package". `README.md` is no longer only a feature blurb: it documents requirements and
setup (`uv sync`, `just migrate`, `just start`), environment configuration (`DATABASE_URL`,
`LOG_LEVEL`, and which commands load `.env`), the lint/type-check/test commands and the
100%-coverage rule, migrations, deployment and rollback, backups and restore, logging, and the
placeholder authentication, linking to `deploy/README.md` for the full procedures. The CDN
assets in `src/meals/web/core.py` are pinned to exact versions (Tailwind `3.4.19`, HTMX
`2.0.2` with the explicit `dist/htmx.min.js` path, Alpine `3.17.5` with `dist/cdn.min.js`)
instead of Alpine's floating `3.x.x` and the unpinned Tailwind Play CDN; the web snapshots
were updated (only the three `src` attributes changed), and
`test_frontend_assets_are_pinned` asserts the exact versions so they cannot drift again.
Vendoring the three files and serving
them from FastAPI remains an option if CDN access becomes a problem, but pinning removes the
unreviewed-upgrade risk without adding an asset build.

- The `filterwarnings` comment in `pyproject.toml` says "except from mymodule" but the
  pattern is `meals.*` — stale copy-paste.
- `README.md` is a feature blurb only; add prerequisites/setup, how to run the dev server
  (`just start`), test/lint commands, and the deployment/migration/backup notes from
  Admin items 1, 2 and 4.
- Front-end assets load from CDNs with floating versions (Alpine `3.x.x`, unpinned
  Tailwind). For an internal Tailscale app the supply-chain/reproducibility risk is low,
  but pinning or vendoring avoids surprise breakage when the CDN changes.

### 9. Refresh dependencies — P2 (done)

**Done:** ran `uv lock --upgrade` / `uv sync` and raised the lower bounds in
`pyproject.toml` to the proven versions. The upgrade surfaced five pieces of fallout, all
fixed:

- **htmy 0.8 → 0.13**: `html.<tag>` is now a `Tag`/`TagWithProps` *instance*, not a type, so
  every `-> html.div`-style return annotation became `-> ComponentType`; `html.meta.charset()`/
  `html.meta.viewport()` moved to `html.Meta.charset()`/`html.Meta.viewport()`; a `Tag` is no
  longer a component, so `_common_recipe`'s list is `list[ComponentType]`. Empty `<script>`
  tags also render on one line now, so five web snapshots were updated.
- **SQLAlchemy 2.1**: `filter_by(user_pk=...)` against a joined `select` now raises
  `AmbiguousColumnError`, so `PlanRepository.summarise` uses `.where(StoredRecipe.user_pk == ...)`.
- **SQLAlchemy 2.1 moved `greenlet` into the `asyncio` extra**: the app now depends on
  `sqlalchemy[asyncio]` (bare `sqlalchemy` no longer installs the async engine's runtime).
- **FastAPI 0.146 treats an empty form value as "missing"**: the string `Form()` fields a user
  can leave blank (`name`, `instructions`, `finish_time`, `steps`, `meal`) now default to `""`,
  and those parameters moved after the injected dependencies so the defaults stay last.
- **Ruff 0.17**: `CPY001` (copyright notice) is ignored; `PLR0917` was added to the existing
  `update_recipe` noqa; `tests/test_api.py` now uses `import datetime as dt` (ICN001).

The pydantic-V1 warning noted below is gone (`import meals.app` is clean under `-W error`).

`pyproject.toml` uses permissive lower bounds and `uv.lock` pins the actual versions, so
the lockfile is the thing that has drifted. Snapshot comparison against PyPI taken in
October 2026 (re-check with `uv lock --upgrade` before acting):

| Package | Locked | Latest |
| --- | --- | --- |
| fastapi | 0.119.0 | 0.143.5 |
| sqlalchemy | 2.0.44 | 2.1.5 |
| pydantic | 2.12.3 | 2.14.1 |
| pydantic-yaml | 1.6.0 | 1.7.0 |
| fasthx | 3.0.1 | 3.2.2 |
| htmy | 0.8.2 | 0.13.5 |
| aiosqlite | 0.21.0 | 0.22.1 |
| python-multipart | 0.0.20 | 0.0.32 |
| ruff | 0.14.1 | 0.17.1 |
| import-linter | 2.5.2 | 2.15 |
| pytest | 8.4.2 | 9.1.1 |
| pytest-asyncio | 1.2.0 | 1.4.0 |
| pytest-cov | 7.0.0 | 7.1.0 |
| pytest-randomly | 4.0.1 | 5.0.0 |
| inline-snapshot | 0.31.0 | 0.36.1 |
| time-machine | 3.1.0 | 3.5.1 |
| uvicorn (transitive) | 0.38.0 | 0.54.0 |
| typer (transitive) | 0.19.2 | 0.27.3 |
| rich (transitive) | 14.2.0 | 15.0.0 |

Run `uv lock --upgrade`, `uv sync`, then `just` and fix any fallout. Expect the most
trouble from the **major** bumps — pytest 9, pytest-randomly 5, uvicorn 0.54, rich 15 —
and from **htmy 0.8 → 0.13** and **SQLAlchemy 2.1** / **FastAPI 0.143**, which are the
libraries the app is built on. Consider doing this *after* the pyrefly migration (Admin
item 11) so the two sources of change are not tangled, and do it on a branch with the
full test suite and snapshot updates reviewed. Raise the lower bounds in `pyproject.toml`
once the upgraded set is proven, to avoid silently resolving back to old versions.

One concrete win from the pydantic bump: FastAPI 0.119.0 imports `pydantic.v1` at import
time, so pydantic 2.12.3 emits `Core Pydantic V1 functionality isn't compatible with
Python 3.14 or greater` on every start. Pydantic 2.14.1 no longer emits it (verified in an
isolated environment with FastAPI 0.119.0); the app uses v2 models only, so the warning is
cosmetic until then.

### 10. Migrate from mypy to pyrefly — P1 (done)

**Migrated:** `uv run pyrefly check` (strict) is now the `just type_check` target and the only
type checker in the `typing` group; `mypy` and `[tool.mypy]` are gone. Config lives in
`[tool.pyrefly]` — `preset = "strict"`, `check-unannotated-defs = true`, a `tests/**`
sub-config relaxing `implicit-any`, and the mypy-strict extras (`no-any-return`,
`incompatible-comparison`, `untyped-function-decorator`, `untyped-class-decorator`,
`implicit-reexport`) under `[tool.pyrefly.errors]`. The three mypy `# type: ignore` comments
were replaced by `@override` plus two `# pyrefly: ignore[bad-override]`s, or a real fix
(a plain tuple in `PlanRepository.summarise`).

The type checker of choice is now Pyrefly (v1.x; 1.4.0 at time of writing), and the
repository is already half-prepared: `pyproject.toml` has a `[tool.pyrefly]` section
(currently only `project-excludes`), but there is no pyrefly dependency or `just` target.
Migrate deliberately, because mypy and pyrefly strict modes are not equivalent:

1. `uv add --dev pyrefly` (add to the `typing` group) and keep mypy installed until the
   migration is green, so both checkers can run side by side while you review the
   differences.
2. Run `pyrefly init` to convert `[tool.mypy]`. **Read the generated config before
   committing it** — not every mypy option has an equivalent and unmapped ones are skipped
   silently. Set `preset = "strict"` (mypy's `strict = true` maps incompletely to
   pyrefly's `preset = "legacy"` plus overrides) and explicitly verify
   `check-unannotated-defs = true`, which mypy's strict bundle enables via
   `check_untyped_defs`.
3. Watch out for the two mypy plugins in `[tool.mypy]`. `pydantic.mypy` is replaced by
   pyrefly's **built-in** Pydantic v2 support (no config needed).
   `sqlalchemy.ext.mypy.plugin` has **no pyrefly equivalent** — pyrefly does not run
   arbitrary plugins. Validate the `Mapped[...]`/`mapped_column` models in
   `src/meals/database/models.py` carefully; add explicit annotations or targeted
   `# pyrefly: ignore` comments where inference degrades.
4. The per-module `[[tool.mypy.overrides]]` for `tests.*` (relaxing `disallow_untyped_*`)
   does not translate directly. Pyrefly sub-configs (`[[sub-config]]`) match **file paths**
   and only support a small set of settings (`errors`, `check-unannotated-defs`,
   `infer-return-types`, `replace-imports-with-any`,
   `ignore-errors-in-generated-code`). Re-express the tests relaxation as a
   `tests/**` sub-config and accept that `disallow_untyped_calls` has no equivalent.
5. Mypy's bracketed ignores (`# type: ignore [override]`, e.g. in `src/meals/schemas.py`)
   are **not portable** — pyrefly uses `# pyrefly: ignore`. Use `pyrefly suppress` to add
   ignores in bulk if needed, then remove them by hand once the underlying errors are fixed.
6. Update the tooling that still names mypy: the `type_check` target in `justfile`,
   `AGENTS.md` (the "mypy strict" constraint and the `just type_check` description), and
   the `typing` dependency group in `pyproject.toml`. Add a `pyrefly check` target to the
   `justfile` so it sits alongside lint and test.
7. Once green, remove `mypy` from the dependencies and delete `[tool.mypy]` plus any now-
   unused mypy ignores, then confirm `pyrefly check` stays clean with the coverage gate
   still passing.

### 11. Run upgrades side-by-side (blue/green) rather than in place — P1 (done)

The app is always running on the Pi, so rather than stopping it, editing the checkout, and
hoping a migration works, build and validate a candidate copy **next to** the live app, then
do a short cutover. This is the practical answer to "upgrade without risking the data or long
downtime", and it composes with Admin items 1 and 2.

**Tooled:** `just candidate` starts/refreshes a candidate worktree on `:8001` against a copy
of the live DB (`scripts/candidate.sh`, `deploy/meals-next.service`); `just candidate promote`
takes a fresh live backup, fast-forwards the live checkout, restarts it (migrations run in
`ExecStartPre`), health-checks and stops the candidate; `just candidate stop` / `clean` retire
it. Exercised on the Pi 2026-10-18 (`just candidate`, then `just candidate promote`).

How it works, and why it is shaped this way:

- The candidate is a second git worktree (`/home/galeb/meals-next`) with its own `.env`, its
  own **copy** of the database and port `8001`. Only one process may write a given SQLite
  file, so the candidate never opens the live file; `scripts/candidate.sh` refuses to start it
  if its `DATABASE_URL` resolves to the live path. The candidate installs runtime dependencies
  only (`--no-dev`).
- Migrations are exercised against the copy, where a failure costs nothing, before live is
  touched.
- `promote` migrates the **live** database in place after a fresh verified backup rather than
  promoting the copy, because the live database may have changed since the copy was taken.
  Downtime is the restart plus the migration.
- Rollback is the previous commit plus the pre-cutover backup, both kept on disk.

The step-by-step procedure, the safety rules and the candidate smoke checklist are in
`deploy/README.md` → "Side-by-side (blue/green) candidate".

---

## Architecture & Testing

Structural notes that are not bugs themselves but make bugs more likely or harder to
catch. Items here are numbered `Arch N`.

### 1. Web routes reimplement API/domain logic — P1 (done)

**Fixed:** added `src/meals/services.py` (a `RecipeService`, `PlanService`, and `TimingsService`
built from the repositories via FastAPI dependencies). Both `meals.api` and `meals.web` now call
these use cases; the HTTP layers only translate requests/responses and map domain errors
(404/409) to responses. The shared `clean_ingredients` helper in `meals/web/core.py` centralises
the blank-ingredient rule that bug 7 was a symptom of. The import-linter layer now reads
`["meals.api | meals.web", "meals.services", "meals.database"]`.

`src/meals/web/*.py` does more than render: `new_recipe` and `update_recipe` parse forms
and build requests, and `update_planned_day` looks a recipe up then updates the plan. The
`new_recipe`/`update_recipe` blank-ingredient divergence (bug 7) is a direct symptom of
this copy-paste. Introduce a small service/use-case layer (or at least shared helpers) that
both `meals.api` and `meals.web` call, so validation and business rules live in one place
and the HTTP layers stay thin. This is the root-cause fix behind several bugs above.

### 2. Response models silently rely on eager-loaded relationships — P2 (done)

**Fixed:** the load options now live in `RECIPE_LOAD_OPTIONS` and `PLANNED_DAY_LOAD_OPTIONS`
in `src/meals/database/repository.py`, and every query that can return an object a response
model serialises uses them (`RecipeRepository.get`/`get_by_name`/`get_all`/`is_like`,
`PlanRepository.update`/`get_range`). The rule — every response relationship must be
eager-loaded, and new ones must be added to the matching constant — is documented beside
the shared load options in `src/meals/database/repository.py` and in `AGENTS.md`.
`tests/test_database.py` adds a test that detaches the ORM objects before Pydantic
validation, so a missing load fails as `DetachedInstanceError` rather than
`MissingGreenlet`; the existing API/web tests already hit each endpoint with related data.

Repositories return ORM objects that Pydantic `from_attributes` models serialize, so
correctness depends on `lazy="selectin"`/`joinedload` being set everywhere the model
touches. A new relationship accessed during serialization raises `MissingGreenlet` (async
lazy-load) at runtime, usually as a 500. Document the "eager-load every relationship a
response model touches" rule (in the repository docstring or `AGENTS.md`) and/or add a test
that hits each endpoint after creating related data. Consider centralizing the load options
instead of repeating them per method.

### 3. `schemas.py` is a single grab-bag module — P2 (done)

**Fixed:** `src/meals/schemas.py` is now a package split by domain: `users.py`,
`recipes.py` (including the ingredient parser and its regex/error constants), `timings.py`,
and `planner.py`. `schemas/__init__.py` re-exports every public name, so existing
`from meals.schemas import ...` and `from meals import schemas` imports, the API/web/CLI
call sites, and the tests are unchanged. There are no cross-domain imports; the two
`pyrefly: ignore[bad-override]` comments on the `RootModel` iterators moved with their
models. Coverage remains at 100% and `schemas/__init__.py` is exercised through the existing
suite.

All user, recipe, ingredient, timing, and planner models live in one file
(`src/meals/schemas.py`). As labels and non-recipe meals land this will grow unwieldy.
Split into a `meals/schemas/` package by domain (users, recipes, timings, planner) with a
re-exporting `__init__` so import sites stay stable.

### 4. `PageRegistry` + import-side-effect registration is fragile — P3

`src/meals/web/core.py` defines a class-level registry keyed by page name, and each page
module registers itself when imported (`meals/web/__init__.py` imports them purely for that
side effect). Nav ordering depends on import order, and forgetting to add a module to
`__init__.py` silently drops its page. Document the convention prominently and/or register
pages explicitly, and add a test asserting the expected set of pages is registered.

### 5. Import-linter contract doesn't cover the non-layered modules — P3

The single contract only constrains `meals.api | meals.web` vs `meals.database`. `meals/auth.py`,
`meals/schemas.py`, and `meals/exceptions.py` sit outside it, so nothing stops
`meals.database` (or `meals.schemas`) from importing web/API helpers. Add a contract that
the database/core modules may not import the web or API layers, and decide explicitly where
`auth.py` belongs in the layering.

### 6. Test fixtures mutate the global app and never clean up — P2

`test_app` in `tests/conftest.py` sets `app.dependency_overrides[get_db]` on the
module-global `app` and never clears it. With `pytest-randomly` reordering tests this is a
latent hazard, and it is what makes the suite unable to run in parallel. Clear the
override in teardown, or build a fresh `FastAPI` instance per test.

### 7. Test DB session doesn't mirror production transaction handling — P2

Production `get_db` yields a session inside `session.begin()` (committing on exit); the test
override yields a bare, shared session and only `flush()` is exercised. Commit/rollback
behaviour and per-request session isolation are therefore never tested — which is how the
`no_autoflush` ingredient bug (bug 3) survived 100% coverage. Adopt the documented
SQLAlchemy "join an external transaction" test pattern so the app runs against a
per-request session that rolls back after each test.

### 8. Full-page external snapshots are brittle and opaque — P2

`inline-snapshot` stores entire HTML documents under `tests/__inline_snapshot__/` keyed by
UUID, so any layout change rewrites whole blobs and the diffs are hard to review. Prefer
targeted assertions (substring or DOM-parsed checks for the behaviour under test) and
reserve snapshots for small, meaningful fragments. The `feat/labels` branch already moved
toward this with `tests/api_assertions.py` (Repo Admin item 8) — align with that approach.

### 9. 100% coverage is hiding gaps behind `# pragma: no cover` — P2

Some pragmas look suspicious: `CreateRecipes.__iter__` is excluded while the identical
`Recipes.__iter__` is covered, and `repository.py` has `# Not possible` branches that may
in fact be reachable. Meanwhile the bugs found by manual probing (duplicate ingredients,
rename collisions, missing pks) show line coverage does not catch negative paths. Audit the
pragmas, add edge/negative-path tests, and confirm each excluded branch is genuinely
unreachable or delete the dead code.

### 10. Split the large test modules by domain — P3 (done)

**Done:** Replaced `tests/test_api.py` and `tests/test_web.py` with packages split by
domain: `tests/api/{test_health,test_users,test_recipes,test_timings,test_planner}.py` and
`tests/web/{test_pages,test_recipes,test_timings,test_planner}.py`. Shared fixtures stay in
`tests/conftest.py`; the external HTML snapshots moved with their tests to
`tests/web/__inline_snapshot__/test_<module>/...`, and
`.inline-snapshot/files_using_external.txt` was regenerated. Removed the stale
`tests/api_tests/` cache directory and the unused `TestNewRecipeAPI.test_name_is_none`
snapshot. Added Alpine/JS contract tests for timings in `tests/web/test_timings.py` covering
the serialized initial state (including quote/HTML escaping), store wiring, add/remove step
controls, and the finish-time offset calculation. The suite is now 129 tests at 100% branch
coverage. No JS runtime dependency was added, so the script is asserted at the Alpine
contract level rather than executed.

`tests/test_api.py` (~570 lines) and `tests/test_web.py` (~350 lines) group everything by
transport. Split by domain (recipes, users, timings, planner) as the app grows; the
`feat/labels` restructure into `tests/api_tests/` is a starting point. Also add coverage for
the timings Alpine/JS behaviour, which is currently untested.

---

## Features

New capability, taken up **after** the remaining Bugs and Arch items at the same priority
(see the note under "Priorities" above).

### 1. Recipe labels and planner filtering — P1

`PLAN.md` describes labels like `carb::pasta`, `meat::chicken`, `time::quick`, and
`toddler::approved` that can filter the planner table, and `recipes.yaml` already contains
`labels: [{category: meat, sub_category: beef}, ...]`. Build the end-to-end feature:
persist labels, expose them on create/update/response schemas and the API, display/edit
them in the recipe and new-recipe forms, show them on recipe cards, and let the planner
filter candidate meals by label. Reuse the `feat/labels` branch (Repo Admin item 8) where
possible instead of starting over.

### 2. Additional (non-recipe) meals — P1

`PLAN.md` calls for "ability to add additional meals that are not recipes" so things like
"Take Away" can be planned without a recipe or ingredients. Today this is faked by creating
recipes with no ingredients/instructions, which also makes them appear in recipe lists
(and as an empty card). Introduce a first-class concept for these (a flag or separate
table), support creating them from the planner, and make sure they still appear in the
summary table's counts.

### 3. Planner navigation and day controls — P1

`src/meals/web/planner.py` always renders the seven days starting from today with no way
to look at another week or clear a day. Add previous/next week navigation (and a "jump to
today"), highlight the current day, and allow clearing/removing a planned meal. While
there, fix the off-by-one where `weeks_plan` calls `repo.get_range(today, today + 7)`
(inclusive) but only renders seven days.

### 4. Shopping list for the planned week — P2

Given a week's planned recipes, aggregate their ingredients (summing quantities where
units match) into a shopping list users can tick off or copy. This is the natural next
step after the planner and the ingredient model already stores `quantity` + `unit`. Add an
API endpoint plus a web view, and handle unit mismatches sensibly.

### 5. Recipe search, sorting, and deletion — P2

There is no way to delete a recipe and no search UI beyond the planner autocomplete
(`RecipeRepository.is_like`). Add a delete endpoint with a confirmation flow in the web UI,
plus search/filter (by name and, once available, label) and sorting on the recipe list.
Consider how deletion interacts with existing planned days.

### 6. Recipe import/export — P2

The app already seeds from `recipes.yaml`. Add an API/UI path to export recipes (JSON or
YAML) and import them back, which doubles as a backup mechanism (Repo Admin item 4) and
makes the seed script less special-cased.

### 7. Timings improvements — P2

`TimingsRepository` allows exactly one timing set per user. Consider named/multiple
timings, associating a timing with a specific recipe, and persisting the active roast. The
`recalculate()` stub and `calculateTimeString` logic in `src/meals/web/timings.py` would
benefit from tests (the JS behaviour is currently untested).

### 8. Authentication improvements — P3

Beyond the hardening in bug 5, this is optional given the Tailscale-only, single-user
setup. If it becomes useful (e.g. session persistence so the browser stops re-prompting,
or a second household device), prefer a lightweight signed session cookie over a full
signup/login system. If you do add UI, make the page routes consistently require auth (bug
8) and redirect rather than issuing HTTP 401s.

### 9. Observability endpoint — P3

Add a richer health/readiness endpoint (database connectivity, version, disk space — useful
on a Pi with an SD card) alongside the existing `/health`. Pairs with the logging work in
Repo Admin item 5.
