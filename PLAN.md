# Planning Document

## Purpose

This document is the roadmap and design record for the meal planner. It is deliberately
more detailed than a wish list: each feature records the decisions made, the data model, the
API and UI surface, and how it will be tested and rolled out. `TODO.md` remains the
prioritised work queue; this file explains **how** a feature will be built.

Current state (October 2026):

- The planner MVP is working: a seven-day plan (`/plan.html`), recipe autocomplete
  (`/meals`), a recipe summary table (`/summary`), recipe CRUD, and the roast timings view.
- The schema is owned by Alembic (`migrations/`, head `0cba625154a2`).
- The app is single-user, self-hosted on a Raspberry Pi, reachable over Tailscale.
- The labels backend on `origin/feat/labels` was never merged. It is archived at tag
  `archive/feat-labels` and is a **reference only**; the implementation starts fresh from
  `master` on the current `feat/labels` branch.

### Branch status

- The local `feat/labels` branch was recreated from `master`; the old WIP tip is preserved by
  the `archive/feat-labels` tag and the `origin/feat/labels` ref.
- `origin/feat/labels` still points at the archived WIP. Once the rewrite is green and
  reviewed, replace it with `git push --force-with-lease origin feat/labels` (or push it under
  a new remote name and retire the old one).
- `PLAN.md` is the first commit on the new branch; implementation proceeds milestone by
  milestone, with `just` green at each merge point.

## Feature: Recipe labels and filtering (next)

### Summary

Give every recipe a set of `category::sub_category` labels (for example
`meat::beef`, `time::quick`, `toddler::approved`) and let the recipe list and the recipe
summary table be filtered by them. Labels are edited on the new/edit recipe forms with a chip
input that autocompletes from the existing vocabulary.

### Goals

- Store labels in normalised, deduplicated tables rather than as free text on each recipe.
- Expose labels on recipe create, update, and response payloads.
- Let a user create labels on the fly; existing categories and subcategories are suggested.
- Filter the recipe list and the recipe summary by selected labels, with predictable
  multi-label semantics.
- Seed labels from `recipes.yaml` via `meals-seed`.
- Ship with an Alembic migration, 100% coverage, and a safe deploy path.

### Non-goals (this pass)

- Labels on planned days or on non-recipe meals. Labels belong to recipes; when additional
  meals land (TODO Features item 2), that feature will decide how they are labelled.
- Filtering the planner's meal picker or the planned week table. The filter applies to the
  recipe list and the recipe summary only.
- A label administration screen (rename, delete, merge, prune unused labels). The vocabulary
  is append-only for now; unused labels are harmless.
- Per-user label vocabularies. The taxonomy is global, like `ingredients`.
- Multi-label boolean expressions beyond OR-within-category / AND-across-categories.

### Decisions

| Topic | Decision |
| --- | --- |
| What carries labels | Recipes only |
| Filter targets | Recipe list and recipe summary table |
| Multi-label semantics | OR within a category, AND across categories |
| Vocabulary | Free-form, created on demand, normalised |
| Editing UI | Chip input with autocomplete from existing labels |
| Label length | 20 characters per category and per subcategory |
| Case | Lowercase; input is normalised rather than rejected |
| Storage | `categories`, `sub_categories`, `recipe_labels` join table |
| Dev database | Back up, drop the stale experiment label tables, recreate via Alembic |

### Canonical label format

A label is written `category::sub_category` everywhere it is shown or exchanged, for example
`meat::beef`. The double colon is the only separator, so neither part may contain a colon.

Normalisation applies to the category and the subcategory independently:

1. Trim leading and trailing whitespace.
2. Lowercase.
3. Collapse internal whitespace runs into a single hyphen (`Toddler Approved` →
   `toddler-approved`).
4. Reject if empty.
5. Reject if longer than 20 characters.
6. Require `^[a-z0-9]+(?:-[a-z0-9]+)*$` — letters, digits, and single hyphens between
   groups. No underscores, punctuation, leading/trailing hyphens, or double hyphens.

Validation errors are reported per field so the existing form error formatter can say
`Issue with label 2: ...`. Duplicate labels are detected **after** normalisation, so
`Meat::Beef` and `meat::beef` in one request are a 422.

### Data model

| Table | Columns | Constraints |
| --- | --- | --- |
| `categories` | `pk`, `name` (`String(20)`, not null) | unique `name` |
| `sub_categories` | `pk`, `name` (`String(20)`, not null), `category_pk` (not null) | FK `category_pk` → `categories.pk` `ON DELETE CASCADE`; unique `(category_pk, name)` |
| `recipe_labels` | `pk`, `recipe_pk` (not null), `sub_category_pk` (not null) | FK `recipe_pk` → `recipes.pk` `ON DELETE CASCADE`; FK `sub_category_pk` → `sub_categories.pk` `ON DELETE CASCADE`; unique `(recipe_pk, sub_category_pk)`; index on `sub_category_pk` |

ORM relationships:

- `StoredRecipe.labels` → `list[StoredRecipeLabel]`, `cascade="all, delete-orphan"`.
- `StoredRecipeLabel.recipe` → `StoredRecipe`; `StoredRecipeLabel.sub_category` →
  `SubCategory`.
- `SubCategory.category` → `Category`; `SubCategory.recipe_labels` →
  `list[StoredRecipeLabel]`, `cascade="all, delete-orphan"`.
- `Category.sub_categories` → `list[SubCategory]` (not a single item).

Constraint names follow the existing convention (`uq_…`, `fk_…`) rather than the archived
branch's `_recipe_label_uc`. The column is `sub_category_pk` rather than the branch's
`label_pk` so the join target is explicit.

Because foreign keys are now enforced (`PRAGMA foreign_keys=ON`), the cascades are not
decorative: deleting a recipe removes its `recipe_labels` rows, and deleting a category
removes its subcategories and their recipe links.

### Eager loading

`RecipeResponse` serialises `recipe.labels`, and each label serialises its subcategory and
category. Extend `RECIPE_LOAD_OPTIONS` in `src/meals/database/repository.py`:

```python
joinedload(StoredRecipe.labels)
.subqueryload(StoredRecipeLabel.sub_category)
.subqueryload(SubCategory.category)
```

Every query that can return a recipe for serialisation already passes the load options. Do
not add `lazy="selectin"` to the label relationships; keep loading explicit and consistent
with `AGENTS.md`. Add a test that detaches the ORM object before validation so a missing load
fails as `DetachedInstanceError`, matching the existing recipes/ingredients test.

### API

Schemas live in a new `src/meals/schemas/labels.py`, re-exported from
`src/meals/schemas/__init__.py` (which keeps import sites stable):

- `CreateLabel(category, sub_category)` — normalising validators.
- `LabelResponse(category, sub_category)` — `from_attributes=True` and validation aliases
  (`AliasPath("sub_category", "name")` for `sub_category`,
  `AliasPath("sub_category", "category", "name")` for `category`) so it validates directly from
  `StoredRecipeLabel`. No join-row `pk`; `__str__` returns the canonical
  `category::sub_category` form.
- `Labels(RootModel[list[LabelResponse]])` — sorted by category then subcategory. If it
  implements `__iter__` for ergonomics, give it the same `@t.override`/pyrefly treatment as
  `Recipes.__iter__` in `schemas/recipes.py`.
- `LabelFilter` — a small value object built from a list of `category::sub` strings. It
  parses, normalises, deduplicates, and groups by category; it raises a clear `ValueError`
  for malformed tokens. Both the API and the web layer use it.

`RecipeResponse` (in `schemas/recipes.py`) gains `labels: list[LabelResponse] = []`.
`CreateRecipeRequest` and `UpdateRecipeRequest` gain
`labels: list[CreateLabel] = Field(default_factory=list)` plus the duplicate-after-normalisation
validator. `LABEL_LENGTH = 20` lives in `src/meals/constants.py`.

`PUT /api/v1/recipes` replaces the whole label set, so omitting `labels` clears it. The web edit
form always round-trips the current set. Give `StoredRecipe.labels` a deterministic
`order_by` (for example `StoredRecipeLabel.sub_category_pk`) so response snapshots do not
depend on join order.

Endpoints:

| Method | Path | Change |
| --- | --- | --- |
| `POST` | `/api/v1/recipes` | Accept `labels`; return them |
| `PUT` | `/api/v1/recipes` | Accept `labels`; replace the set; return them |
| `GET` | `/api/v1/recipes/{pk}` | Include `labels` |
| `GET` | `/api/v1/recipes` | Optional repeated `labels` query parameters; filter the result |
| `GET` | `/api/v1/recipes/` (by name) | Include `labels` |
| `GET` | `/api/v1/recipes/like/` | Include `labels` |
| `GET` | `/api/v1/labels` | New: the full taxonomy, sorted, for autocomplete and clients |
| `GET` | `/api/v1/planned_day/summary/` | Optional repeated `labels` query parameters; filter the rows |

Query format: repeated parameters, one canonical token each, e.g.
`?labels=meat%3A%3Abeef&labels=time%3A%3Aquick`. This matches HTML checkbox serialisation and
avoids defining a second delimiter. Absent or empty means no filter. Malformed tokens are
422. Unknown but well-formed labels are a valid filter that matches nothing (200 with an
empty result), not an error.

Filtering logic is shared by the recipe list and the summary. It selects the recipe pks that
satisfy the filter:

```sql
SELECT rl.recipe_pk
FROM recipe_labels rl
JOIN sub_categories sc ON sc.pk = rl.sub_category_pk
JOIN categories c ON c.pk = sc.category_pk
WHERE (c.name, sc.name) IN (VALUES ...)
GROUP BY rl.recipe_pk
HAVING COUNT(DISTINCT c.pk) = :requested_category_count
```

The outer recipe query then adds `StoredRecipe.pk IN (<subquery>)`. Because a recipe only
needs one match per requested category, this gives OR within a category and AND across
categories. Deduplicate the requested tokens first; `requested_category_count` is the number
of **distinct categories**, not tokens.

Summary-specific rules:

- Keep the existing `day <= today` bound in the outer-join `ON` clause so unplanned matching
  recipes still appear with `count: 0` and `last_eaten: None`.
- Keep the `user_pk` scoping on `StoredPlannedDay` and the recipe.
- The summary response stays `RecipeSummary`; labels are used for filtering, not returned.

### Services

`RecipeService` gains `list(user_pk, *, has_ingredients=True, label_filter=None)`,
`create`/`update` pass the labels through untouched (the repository owns persistence), and
`labels()` returns the taxonomy. `PlanService.summary(user_pk, label_filter=None)` forwards to
the repository. The HTTP layers only parse query/form parameters and map errors; they never
build SQL or touch the session.

Repository responsibilities:

- `_resolve_label_pks(labels)`: upsert categories and subcategories, prefetch in one query
  per table rather than per label, and return deduplicated subcategory pks.
- `create`/`update`: keep master's ingredient handling, duplicate-ingredient validation, and
  the rename-collision `RecipeAlreadyExistsError`. Add/remove `StoredRecipeLabel` rows by
  diffing resolved pks. Return through `self.get(pk, user_pk)` after the flush so the response
  is fully eager-loaded.
- `get_all`/`is_like`/`get`/`get_by_name`: apply the load options and the optional filter.
- A module-private helper builds the matching-pk subquery so `PlanRepository.summarise` and
  `RecipeRepository` cannot drift.

Do not reintroduce the archived branch's `_join_fields`, `populate_existing=True`,
per-ingredient flush loop, or the `# pragma: no cover` branch: master's versions are newer and
must win.

### Web UI

**Recipe cards and sections.** `_common_recipe` in `src/meals/web/core.py` renders the labels
as small chips (`category` muted, `sub_category` emphasised, or the canonical
`category::sub_category` string) between the title and the ingredients. This applies to both
the read-only and editable sections for free.

**Editing: chip input with autocomplete.** Both the new-recipe form
(`src/meals/web/new.py`) and the edit form (`src/meals/web/index.py`) get the same component:

- Alpine state: `labels: string[]` and `newLabel: string`.
- A text input bound to `newLabel`, with a `<datalist>` of every existing canonical label and
  a placeholder such as `meat::beef`.
- Enter or the "Add label" button normalises the input client-side (trim, lowercase,
  whitespace → hyphen), rejects an empty or duplicate value, and appends it to `labels`.
- Selected labels render as removable chips; removing one filters the array.
- A `<template x-for="label in labels">` emits one
  `<input type="hidden" name="labels" :value="label">` per chip. This matches the existing
  repeated `ingredients` form field, so FastAPI reads `labels: list[str] = Form(default_factory=list)`
  with no JSON or delimiter parsing. The server remains authoritative for normalisation and
  validation.
- Initial state for the edit form comes from `recipe.labels` in the `RecipeResponse`; the new
  form starts empty.
- The new-recipe page and `/recipe/{pk}/edit` need the taxonomy for the datalist. Return a
  small page view model from those routes (for example `NewRecipePage(labels)` and
  `RecipeEditPage(recipe, labels)`) and let the page/component functions accept it; do not do
  database IO inside an htmy component.
- The shared `format_new_recipe_error` maps label validation errors to
  `Issue with label N: ...`.

**Filtering the recipe list.** Replace the two lazy fragments on the recipes page
(`/recipe_list` and `/recipes`) with one `#recipe-panel`:

- The page route (`GET /`) accepts repeated `labels` query parameters so filtered views are
  deep-linkable, and renders the panel directly (no first-load XHR).
- The panel contains a filter bar, the "Contents" links, and the recipe cards.
- The filter bar groups subcategory chips by category. Each chip is a checkbox named `labels`
  with the canonical token as its value; selected chips are server-rendered as checked. This
  maps the checkbox UI directly onto OR-within-category / AND-across-categories: checking two
  chips in one category ORs them; checking chips in another category ANDs the groups.
- A "Clear" control removes all selections.
- The filter form is `hx-get="/recipes"`, `hx-target="#recipe-panel"`,
  `hx-swap="outerHTML"`, and `hx-trigger="change"`. Do **not** use `hx-push-url` here: the
  response is a fragment endpoint, so pushing `/recipes?labels=…` would leave a non-page URL in
  the address bar. Deep links are supported by loading `/?labels=…` directly instead; the
  filter bar is server-rendered from the query string.
  `/recipes` reads the same repeated `labels` parameters and returns the filtered panel.
- With no labels in the database, show a short "Add labels to your recipes to filter
  them" empty state instead of an empty filter bar.
- Filter blank entries server-side with a `clean_labels` helper beside `clean_ingredients`
  in `src/meals/web/core.py`, mirroring how blank ingredient inputs are dropped.
- Remove `/recipe_list` if nothing else uses it; otherwise leave it as a compatibility alias.

**Filtering the summary.** The planner page's summary section gets its own filter control:

- `/summary` accepts repeated `labels` parameters and returns the whole `#recipe-summary`
  section, including the filter bar and the current selection.
- The section is a form with `hx-get="/summary"`, `hx-target="#recipe-summary"`,
  `hx-swap="outerHTML"`, and `hx-trigger="change"`. The existing "Refresh" button becomes the
  form submit (or includes the form), so it preserves the current filter.
- The weekly plan table and the meal picker are unchanged.

Alpine is already loaded. No new JavaScript runtime dependency is added; the behaviour is
asserted at the Alpine contract level (markup, handlers, hidden fields), as done for timings.

**View models.** The filter bar needs the full taxonomy as well as the filtered rows. Rather
than overloading `Recipes` or `RecipeSummary`, use small view models (for example
`RecipePanel(recipes, labels, selected)` and `SummaryPanel(summaries, labels, selected)`) built
in the web layer. `/recipes` injects `RecipeServiceDep` once and calls `list()` and `labels()`;
`/summary` injects `PlanServiceDep` and `RecipeServiceDep`. `summary_table` and the new panel
renderer take these view models. Keep the API responses unchanged (`Recipes`,
`list[RecipeSummary]`).

A malformed deep link (`/?labels=not-a-label`) should render a compact error fragment or fall
back to the unfiltered panel, never a 500; the API returns 422 for the same input.

### Seed data and CLI

`recipes.yaml` already contains label blocks (`labels: [{category: meat, sub_category: beef}]`).
After this feature:

- `SeedRecipe` no longer redefines `labels` as `list[dict[str, str]]`; it inherits the typed
  `CreateRecipeRequest` (or is removed in favour of it).
- `load_recipes` stops warning that labels are unsupported.
- `seed` sends `recipe.model_dump()` (no `exclude={"labels"}`), so labels are created and
  linked on first insert.
- Existing recipes are still skipped by name, so seeding does not backfill labels onto recipes
  that already exist. That is intentional; note it in the CLI help/docstring. A future
  `meals-seed --update` can add backfill if it becomes useful.
- `meals-seed` remains idempotent and safe to re-run.

### Migration and data handling

A new Alembic revision after `0cba625154a2` creates the three tables. Because these are new
tables, no batch mode is needed, but keep `render_as_batch=True` as configured.

Verification before merging:

1. `uv run alembic upgrade head` on a fresh temporary database.
2. `uv run alembic downgrade -1`, then `upgrade head` again.
3. `uv run alembic check` against the models (no drift).
4. Compare `.schema` dumps with the expected model schema.
5. Run the suite (it builds the schema from metadata, not the migration).

Development database (`meals.db` in the checkout): it contains label tables from the earlier
experiment, has no `alembic_version`, and predates the last two revisions (it still has the old
single-column `UNIQUE` constraints on `recipes.name` and `planned_days.day`). Running
`alembic upgrade head` directly would replay the baseline and fail with
`table recipes already exists`. Treat it as a pre-Alembic database and bring it up in order.
Confirm `DATABASE_URL` resolves to the checkout's `meals.db` (it is unset locally, which yields
the relative default) and **not** the live `/home/galeb/meals-data/meals.db` before running
these:

```bash
just backup      # verified copy first (uses the relative meals.db; there is no .env locally)
# The experiment tables are not part of any revision, so remove them first:
sqlite3 meals.db "DROP TABLE recipe_labels; DROP TABLE sub_categories; DROP TABLE categories;"
# The rest of the schema matches the baseline, so stamp it and let Alembic apply the rest:
uv run alembic stamp 8b8ea410224a
just migrate
uv run alembic check
```

This preserves the 35 seeded recipes in the dev database. If `alembic check` reports drift
beyond the expected revisions, the dev database is disposable: delete it, `just migrate` from
scratch, and reseed with `just start` + `meals-seed` (or `uv run meals-seed`).

Production (Pi): the migration is additive and the live database has no label tables, so no
data migration is required. Validate with `just candidate` (a copy of the live DB on `:8001`),
smoke-test labels and filtering, then `just candidate promote` (fresh backup, migrate, restart,
health check). Rollback remains the previous commit plus the pre-cutover backup.

### Testing

Tests are grouped by domain, following `tests/api/` and `tests/web/`:

- `tests/test_schemas.py`: normalisation (trim, lowercase, spaces → hyphens), invalid
  characters, empty, too long, duplicates after normalisation, `LabelFilter` parsing/groups,
  and canonical `str()` output.
- `tests/api/test_recipes.py`: create/update with labels; empty labels; reuse a label across
  recipes; remove one/all labels; response payload includes labels; cross-user scoping; the
  existing snapshots remain valid because `labels` defaults to `[]`.
- `tests/api/test_labels.py`: `GET /api/v1/labels` returns the sorted taxonomy and requires
  auth.
- `tests/api/test_recipes.py` (filter cases): single label; two subcategories in one category
  (OR); labels in two categories (AND); no match; unknown label (200, empty); malformed token
  (422); duplicate tokens; filtered list still respects the user scope.
- `tests/api/test_planner.py`: filtered summary returns only matching recipes, still counts
  only days up to today, keeps unplanned matches at `count: 0`, and is user-scoped.
- `tests/test_database.py`: recipe deletion cascades `recipe_labels`; orphan
  `recipe_labels`/`sub_categories` rows are rejected with foreign keys on; composite
  uniqueness is enforced; detached-object validation fails without the label load options.
- `tests/web/test_recipes.py`: label chips render on cards; filter bar checkboxes and selected
  state; `/recipes?labels=…` returns only matching cards; chip-input markup (datalist, hidden
  `name="labels"`, Alpine add/remove handlers); edit form initial labels; label error
  formatting.
- `tests/web/test_planner.py`: summary filter control and filtered rows.
- `tests/test_cli.py`: seeding sends labels, no skip warning, re-running stays idempotent.
- `tests/test_app.py`: mapper count `6 → 9`.
- `tests/conftest.py`: `sausage_recipe` and `burger_recipe` fixtures with labels.

Coverage stays at 100% (branch coverage); no `# pragma: no cover` in `src/`. Update inline
snapshots only after manually verifying the output. `just` (lint, pyrefly strict, tests) is the
gate.

### Task breakdown

- [ ] **M1 — Schema and storage.** `schemas/labels.py`, request/response fields, normalising
      validators, `constants.py`, models, `RECIPE_LOAD_OPTIONS`, migration, dev-DB reset.
      Add `meals.constants` to the core side of the import-linter contract for consistency.
- [ ] **M2 — Repository, services, API.** Label upsert/diff, shared matching-pk subquery,
      filtered `get_all` and `summarise`, `RecipeService.list/labels`, `PlanService.summary`,
      `GET /api/v1/labels`, query params on the list and summary endpoints.
- [ ] **M3 — Web UI.** Label chips, chip editor with autocomplete, recipe-list filter panel,
      summary filter, error formatting, `/recipe_list` retirement.
- [ ] **M4 — Seeding.** Send labels from `recipes.yaml`, drop the skip warning, keep
      idempotence.
- [ ] **M5 — Verification and rollout.** Full test matrix, `just`, migration checks, candidate
      deploy, TODO/README updates.

### Acceptance criteria

- A recipe can be created and edited with zero, one, or many labels; labels are normalised,
  deduplicated, and returned in every recipe payload.
- The same label can be shared by many recipes; new recipes reuse existing category and
  subcategory rows.
- Selecting two subcategories in one category returns recipes matching either; adding a label
  from another category requires a match in both.
- The recipe list and summary table can be filtered from the UI and by deep link, and the
  selection survives the HTMX refresh.
- Malformed labels fail with a readable 422/form error; unknown labels simply return no rows.
- The migration upgrades, downgrades, and passes `alembic check`; the live data is unaffected.
- `just` passes at 100% coverage.

## Later planner work

These remain from the original plan and are tracked as separate features in `TODO.md`:

- **Additional (non-recipe) meals.** First-class "Take Away"-style meals, planned without a
  recipe or ingredients, still counted in the summary. Decide whether they carry labels when
  this lands.
- **Planner navigation and day controls.** Previous/next week, jump to today, highlight the
  current day, clear a planned meal, and fix the off-by-one in `get_range(today, today + 7)`.
- **Planner filtering.** Extend label filtering to the meal picker and/or the planned week
  table once the recipe list and summary behaviour is proven.
- **Shopping list.** Aggregate the planned week's ingredients, summing quantities where units
  match.
- **Recipe search, sorting, and deletion.** Delete with confirmation, plus search/filter by
  name and label, and sorting on the recipe list.
- **Recipe import/export.** JSON or YAML export/import, doubling as a backup mechanism.
- **Timings improvements.** Named/multiple timing sets, recipe association, and tests for the
  Alpine/JS timing behaviour.
- **Authentication improvements.** A session cookie so the browser stops re-prompting, if it
  ever becomes worth it for the single-user Tailscale setup.
- **Observability endpoint.** Database connectivity, version, and disk space for the Pi.
