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

Before finishing any item run `just` (lint + type_check + test). Coverage is enforced at
100% branch coverage, so every new branch needs a test. Follow the existing test layout
(`tests/test_api.py`, `tests/test_web.py`, `tests/conftest.py`) and update
`inline-snapshot` snapshots only after eyeballing the new output.

## Protect the live data (read this first)

The production database is a single SQLite file living **inside the git checkout** on the
Pi — `galeb@192.168.1.135:/home/galeb/meals/meals.db` — and it holds real data. Treat the
following as prerequisites for Admin items 1–4: no migration, dependency upgrade, or deploy
change should be attempted until they are done.

**Status:** step 1 (backup) is done — copies exist on the Pi and locally. Steps 2–5 are
outstanding. Note that the existing backup is a point-in-time snapshot and will not include
later edits to the app's data, so **refresh it (step 1) before every migration or deploy**;
do not treat it as permanently done.

- [x] **1. Back up using SQLite's backup API — not `cp`.** A backup has been taken and copies
  are held on the Pi and locally. For future refreshes, copying a live database with `cp` can
  capture a torn file and misses the `-wal`/`-shm` sidecars, so use
  `sqlite3 /home/galeb/meals/meals.db ".backup '/home/galeb/meals-backups/meals-$(date +%F-%H%M).db'"`
  (or, if the `sqlite3` CLI isn't installed on the Pi, Python's `sqlite3.Connection.backup`).
  Verify a copy by opening it read-only and counting rows (`users`, `recipes`,
  `recipe_ingredients`, …), and keep at least one copy off the Pi.
- [ ] **2. Move the database out of the checkout** to a stable absolute path (e.g.
  `/home/galeb/meals-data/meals.db`, or `~/.local/share/meals/`). The file is
  `*.db`-gitignored, so a `git clean -fdx`, a fresh clone, or a deploy script that rsyncs
  with `--delete` will silently destroy it. This depends on Admin item 3 (env-driven
  `DATABASE_URL`); point the app **and** Alembic at the same absolute path.
- [ ] **3. Never let the test suite or dev tooling point at production.** Right now
  `tests/test_app.py::test_lifespan_init_models` runs `init_models()` (i.e. `create_all`)
  against the *relative* `meals.db` in the current directory, so running `just test` from
  `/home/galeb/meals` touches the live file. Make the path an env var that tests override
  to `tmp_path`, or set `DATABASE_URL` before importing the app. Also delete or guard the
  commented-out `Base.metadata.drop_all` line in `src/meals/database/session.py` — a stray
  uncomment would wipe the database.
- [ ] **4. Adopt Alembic against the real schema, don't recreate it.** Generate the initial
  migration from the current models, then run `alembic stamp head` on the existing
  database (marking it as already migrated) instead of `upgrade`, so Alembic never tries to
  re-create the tables that are already there. Test the first real migration on a **copy**
  of the live DB before running it in place. This matches Admin item 2.
- [ ] **5. Make the deploy flow backup-then-migrate, and rollback a file swap.** `just deploy`
  should take a verified backup before running migrations; the documented restore path is:
  stop the service, restore the `.db` file (and remove any stale `-wal`/`-shm`), start the
  service, verify. Keep the previous release on disk so a code rollback is a checkout and
  restart, not a rebuild. See Admin item 12 for the side-by-side version of this.

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
| Admin 11 — migrate mypy → pyrefly | P1 |
| Admin 12 — side-by-side (blue/green) upgrades | P1 |
| Bug 9 — `hx-ext="json-enc"` never loaded | P2 |
| Bug 1 — global uniqueness constraints | P2 (latent) |
| Bug 4 — cross-user planned-day auth hole | P2 (latent) |
| Bug 5 — passwords never checked | P2 (hardening) |
| Bug 11 — SQLite foreign keys not enforced | P2 |
| Bug 12 — brittle ingredient parsing | P2 |
| Admin 5 — logging / exception handler | P2 |
| Admin 6 — seed/CLI scripts | P2 |
| Admin 7 — `.gitignore` / `AGENTS.md` | P2 |
| Admin 8 — `feat/labels` branch triage | P2 |
| Admin 10 — refresh dependencies | P2 |
| Admin 9 — tooling/documentation tidy | P3 |
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

### 1. (Latent) Uniqueness constraints are global, not per-user — P2

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

### 2. Renaming a recipe onto an existing name raises a 500 — P1

`RecipeRepository.update` (`src/meals/database/repository.py`) never checks for a name
collision, even though `create` does. Updating a recipe so its `name` matches another of
the user's recipes returns an unhandled `IntegrityError` instead of a 409.

Reproduction (confirmed): create two recipes, rename one to the other's name →
`UNIQUE constraint failed: recipes.name`.

This affects the single user directly (e.g. tidying up duplicates). Return
`RecipeAlreadyExistsError` (the route already maps it to 409) or otherwise handle it, and
add an API test.

### 3. Duplicate ingredient name within one request raises a 500 — P1

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

### 4. (Latent) Cross-user authorization hole in `POST /api/v1/planned_day` — P2

`PlanRepository.update` blindly sets `planned.recipe_pk = planned_day.recipe.pk` without
verifying the recipe belongs to the requesting user. Any authenticated user (i.e. anything
on the tailnet) can plan a recipe that belongs to someone else by supplying its `pk`.

Reproduction (confirmed): user two posts `{"day": "2025-01-01", "recipe": {"pk": 1, ...}}`
using user one's recipe pk → 201, and the plan is stored.

Only relevant once there is more than one user. Verify recipe ownership in the
repository/route (404/403 on mismatch) and also scope `PlanRepository.summarise` by
`StoredPlannedDay.user_pk` (see bug 6).

### 5. Passwords are never checked (auth is username-only) — P2 hardening

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

### 6. Recipe summary counts future meals — P1

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

### 7. Editing a recipe with a blank ingredient shows a raw validation dump — P1

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

### 8. Page shells are public but their content is authenticated — P1

`index`, `new`, `plan`, and `timings` page handlers in `src/meals/web/*.py` take no
`CurrentUser` dependency, so `GET /`, `/new.html`, `/plan.html`, `/timings.html` render
without auth. The HTMX fragments they load (`/recipe_list`, `/recipes`, `/weeks_plan`,
`/summary`, `/timings`) do require auth, so on first load the browser gets a page whose
content fails with 401 over XHR (which does not reliably trigger a usable Basic-auth
prompt).

For a single user this is a real "why is the page empty?" annoyance every time the session
resets. Either require `CurrentUser` on the page routes too, or add a simple login page
and redirect unauthenticated users to it (ties into bug 5).

### 9. `hx-ext="json-enc"` is used but the extension is never loaded — P2

`save_timing()` in `src/meals/web/timings.py` sets `hx_ext="json-enc"`, but no `json-enc`
script is included in the page layout (`page()` in `src/meals/web/core.py`). HTMX
currently ignores the unknown extension and falls back to form encoding, which is why the
`Form()`-based route works. Confirm the timings "Save" button actually persists edits in a
browser, then either load the extension and switch the route to a JSON body, or drop the
attribute so the markup matches reality.

### 10. Web recipe pages 500 on a missing recipe instead of 404 — P1

`get_recipe` and `edit_recipe` in `src/meals/web/index.py` call `repo.get(pk, user.pk)`
and pass the result (which may be `None`) straight into
`RecipeResponse.model_validate(...)`, which raises a `ValidationError` → HTTP 500. The JSON
API routes already handle this case with a 404. Reproduction (confirmed): `GET /recipe/9999`
and `GET /recipe/9999/edit` raise; they should return a 404 (or a small "recipe not found"
fragment). `update_recipe` already handles the missing case via `RecipeDoesNotExistError`,
so use that as the pattern.

### 11. SQLite foreign keys are not enforced — P2

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

### 12. Ingredient parsing is brittle — P2

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

### 1. A better way to deploy to the Pi — P1

Deployment already runs under systemd, but the unit is **not in the repository**. A
`meals.service` unit exists at `/etc/systemd/system/meals.service` (enabled, started
2026-10-01) whose `ExecStart` is already the production command
`uv run fastapi run src/main.py`, `WorkingDirectory` is the checkout `/home/galeb/meals`, and
it listens on `0.0.0.0:8000` (LAN clients at `192.168.1.x` reach it in the logs). So the
server command itself is fine; the problem is that the unit lives outside the checkout and is
therefore unversioned, undocumented, and easy to lose or drift — `/home/galeb/meals` is not a
pristine clone because of it, and there is no `just deploy`. (`just start` still runs
`fastapi dev`, the auto-reload development server, which is for local work only.) The goal is
to bring the existing unit under version control, harden it, and make the release one command
that survives reboots and upgrades without data loss.

For a single self-hosted service on one Pi, **systemd remains the least machinery and the
recommended path** — it is already the chosen path, so this is consolidation rather than a
rewrite:

- Keep the production command (`fastapi run src/main.py`) with no `--reload`. It currently
  binds `0.0.0.0` and LAN clients use it, so only narrow that to the Tailscale address if you
  actually want LAN access gone; TLS is unnecessary inside Tailscale.
- **Version-control the unit.** A hardened copy is now committed at
  `deploy/meals.service` (with install notes in `deploy/README.md`): explicit `User=`/`Group=`,
  `EnvironmentFile=-/home/galeb/meals/.env`, `Environment=PYTHONUNBUFFERED=1`,
  `ExecStart=.../uv run --frozen fastapi run src/main.py`, `Restart=on-failure`,
  `RestartSec=5`, `SyslogIdentifier=meals`, `NoNewPrivileges=true`, `PrivateTmp=true`.
  Remaining work here is to actually install it on the Pi (`sudo cp deploy/meals.service
  /etc/systemd/system/` then `daemon-reload` + `restart`) and confirm the running service
  matches. Do **not** rely on the working directory for the database path (see Admin item 3).
- Run a verified database backup, then migrations, as `ExecStartPre=` steps (Admin item 2
  and **Protect the live data**), so a restart upgrades the schema safely and a failed
  upgrade can be rolled back by restoring the file.
- Add a `just deploy` target (or `scripts/deploy.sh`) that performs the whole release:
  fetch/rsync the new code, `uv sync --frozen`, run migrations, restart the service, then
  poll `/health` and fail loudly if it doesn't come back. Keeping the previous release on
  disk makes rollback a checkout + restart rather than a rebuild.
- Logs go to journald automatically; document `journalctl -u meals -f` in `README.md`.

A `Dockerfile` + compose file is a reasonable alternative if you want process isolation,
but it adds image build/pull tooling to a job that is otherwise a `git pull` and a
restart. Whichever you choose, document it in `README.md` together with the rollback
procedure and a note that `scripts/plan_meal.py` expects a running server.

Pi-specific details to get right at the same time:

- Set `TZ` in the service environment so `date.today()` and the roast timings reflect local
  time rather than UTC.
- Confirm prebuilt wheels exist for the pinned dependencies on the Pi's architecture
  (`pydantic-core`, `greenlet`, and uvicorn's `uvloop`/`httptools`). Raspberry Pi OS 64-bit
  (`aarch64`) is well supported; 32-bit (`armv7l`) often is not — check before an upgrade.
- Decide on the SQLite journal mode (WAL is kinder to an SD card and to the backup/upgrade
  flow) when foreign keys are enabled (bug 11).

### 2. Data-preserving migrations (Alembic) — P1

`init_models` in `src/meals/database/session.py` only calls `create_all`. Any schema change
currently requires deleting `meals.db` (its own docstring admits this) — and on a
Raspberry Pi that means losing your recipes, plans, and timings. Introduce Alembic with an
initial migration, wire the upgrade step into the deploy flow (Admin item 1), and migrate
the existing database. For the existing database, use the baseline + `alembic stamp head`
approach in **Protect the live data** above so the initial migration marks the
already-present tables as applied instead of trying to recreate them. This is the prerequisite for the labels
work (Features item 1), which adds several tables, and it is the single most valuable item
for data durability.

### 3. Make configuration env-driven — P1

`DATABASE_URL` is hardcoded to the relative path `sqlite+aiosqlite:///meals.db`. Under a
systemd unit or container the working directory is not guaranteed, so this can create or
open the wrong file — silently starting with an empty database. Read `DATABASE_URL` (and
the session/secret key from bug 5, if added) from the environment with a sensible default,
ideally via a small settings object, and add a `.env.example`. Prefer an absolute default
path under a data directory rather than one relative to the repo root, and point the
production service at it from its `EnvironmentFile`.

### 4. Backups / export of `meals.db` — P1

The only copy of your data is a single SQLite file on the Pi. Add a simple, documented
backup path (e.g. a `just backup` target using `sqlite3 .backup`, plus a note about
restoring) and/or the export capability in Features item 6. This is cheap insurance for a
device that is awkward to rebuild. Consider a scheduled copy to another machine on the
tailnet.

### 5. Add logging and a global exception handler — P2

There is no `@app.exception_handler` and no logging configuration; unhandled
`IntegrityError`s surface as bare 500s, and `src/meals/web/new.py` has a
`# TODO: add logging here`. On a headless Pi this makes debugging hard. Add structured
logging that goes to journald (or the container log), a handler for database/validation
errors that returns a clean response, and request IDs.

### 6. Fix the seed/CLI scripts — P2

`scripts/populate_db.py` only seeds recipes, silently drops the `labels` present in
`recipes.yaml` (the current `CreateRecipes`/`CreateRecipeRequest` schemas have no `labels`
field), and never loads `timings.yaml` (whose `end`/`step` keys don't match
`TimingsCreate`'s `finish_time`/`description`). `typer`, `rich`, and `httpx` are used by
the scripts but pulled in only transitively via `fastapi[standard]`, and
`[project.scripts]` in `pyproject.toml` is empty. Give the scripts explicit
dependencies/entry points, make `populate_db.py` also seed timings (reconciling the YAML
keys), and seed labels once they exist. Also note `pydantic-yaml` emits a Pydantic V1
warning on Python 3.14 — check whether an upgrade or alternative is needed.

### 7. Sort out `.gitignore` and untracked guidance — P2

The repo `.gitignore` only covers `__pycache__`, `.venv`, `.coverage`, `*.db`, and
`recipes.yaml` (plus `.env`, added with the Admin item 3 scaffolding). Cache directories
(`.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`,
`.import_linter_cache/`) are currently ignored only by a developer's global git config,
and `AGENTS.md` is ignored globally and therefore **not tracked in the repo**. Decide
whether `AGENTS.md` should be committed (it holds the repository guidelines) and add the
cache/tooling directories (including `.kiro/`) to `.gitignore` so a fresh clone is clean.

### 8. Triage the `feat/labels` branch — P2

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

### 9. Tidy tooling and documentation — P3

- `[tool.pyrefly]` in `pyproject.toml` is currently inert; it is superseded by the
  migration in Admin item 11.
- The `filterwarnings` comment in `pyproject.toml` says "except from mymodule" but the
  pattern is `meals.*` — stale copy-paste.
- `README.md` is a feature blurb only; add prerequisites/setup, how to run the dev server
  (`just start`), test/lint commands, and the deployment/migration/backup notes from
  Admin items 1, 2 and 4.
- Front-end assets load from CDNs with floating versions (Alpine `3.x.x`, unpinned
  Tailwind). For an internal Tailscale app the supply-chain/reproducibility risk is low,
  but pinning or vendoring avoids surprise breakage when the CDN changes.

### 10. Refresh dependencies — P2

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

### 11. Migrate from mypy to pyrefly — P1

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

### 12. Run upgrades side-by-side (blue/green) rather than in place — P1

The app is always running on the Pi, so rather than stopping it, editing the checkout, and
hoping a migration works, build and validate a candidate copy **next to** the live app, then
do a short cutover. This is the practical answer to "upgrade without risking the data or
long downtime", and it composes with Admin items 1 and 2.

1. Take a fresh backup of the live DB (see **Protect the live data**). The backup is what
   makes the final swap reversible.
2. Create a candidate directory (e.g. `/home/galeb/meals-next`) holding the new code and a
   **copy** of the database. Only ever run one process against a given SQLite file — one
   writer at a time — so the candidate must use its own copy, not the live file.
3. Run migrations (Admin item 2) against the candidate copy, then start the candidate on a
   different port, e.g.
   `fastapi run src/main.py --host 0.0.0.0 --port 8001` (reload is off by default; `PORT`
   can be set instead). Reach it over Tailscale at `http://<pi-tailscale-ip>:8001` and
   exercise the changed flows against real data.
4. Cut over: stop the live instance, put the migrated DB in the canonical path (or repoint
   the new app at it via `DATABASE_URL`), and start the new instance on the normal port.
   Because the new database was prepared ahead of time, the only downtime is the process
   restart — seconds, not the length of a migration.
5. Roll back by starting the previous checkout against the backup copy; keep the old
   checkout and DB copy on disk until you're satisfied.
6. Once this is routine, fold it into `just deploy` / the systemd unit (Admin item 1) so a
   cut is one command, and stop exposing the temporary port.

Note the current hardcoded relative `DATABASE_URL` makes step 2/4 awkward (the candidate
must run from a directory where the copy is named `meals.db`); doing Admin item 3 first
makes this clean and explicit. Also make sure the temporary port is only reachable on the
tailnet, and that the two instances never share a database file.

See `migrate_plan.md` for the ordered, executable version of this, including the
prerequisite TODO items and the commands.

---

## Architecture & Testing

Structural notes that are not bugs themselves but make bugs more likely or harder to
catch. Items here are numbered `Arch N`.

### 1. Web routes reimplement API/domain logic — P1

`src/meals/web/*.py` does more than render: `new_recipe` and `update_recipe` parse forms
and build requests, and `update_planned_day` looks a recipe up then updates the plan. The
`new_recipe`/`update_recipe` blank-ingredient divergence (bug 7) is a direct symptom of
this copy-paste. Introduce a small service/use-case layer (or at least shared helpers) that
both `meals.api` and `meals.web` call, so validation and business rules live in one place
and the HTTP layers stay thin. This is the root-cause fix behind several bugs above.

### 2. Response models silently rely on eager-loaded relationships — P2

Repositories return ORM objects that Pydantic `from_attributes` models serialize, so
correctness depends on `lazy="selectin"`/`joinedload` being set everywhere the model
touches. A new relationship accessed during serialization raises `MissingGreenlet` (async
lazy-load) at runtime, usually as a 500. Document the "eager-load every relationship a
response model touches" rule (in the repository docstring or `AGENTS.md`) and/or add a test
that hits each endpoint after creating related data. Consider centralizing the load options
instead of repeating them per method.

### 3. `schemas.py` is a single grab-bag module — P2

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

### 10. Split the large test modules by domain — P3

`tests/test_api.py` (~570 lines) and `tests/test_web.py` (~350 lines) group everything by
transport. Split by domain (recipes, users, timings, planner) as the app grows; the
`feat/labels` restructure into `tests/api_tests/` is a starting point. Also add coverage for
the timings Alpine/JS behaviour, which is currently untested.

---

## Features

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
