# 0004: Use Pydantic schemas as the boundary and eager-load response relationships

- Status: Accepted
- Date: 2026-11-08

## Context

Input reaches the app in several forms: JSON bodies from the API, form fields from the HTMX
pages, YAML from the seed helper, and response JSON parsed by the CLI and tests. Ingredient
strings (``"500g beef"``) and labels (``"meat::beef"``) need the same parsing, normalisation,
and invariant checks wherever they arrive, and invalid input must be rejected before it
reaches the database. The API and the pages also expose the same data, but one serialises it
to JSON and the other renders it to HTML.

SQLAlchemy's async session adds a second constraint. Its relationships can only be loaded
during an awaited query. Pydantic's `from_attributes` validation reads attributes
synchronously, so if a response model touches a relationship that the query did not load,
SQLAlchemy attempts an implicit lazy load outside the async greenlet context and raises
`MissingGreenlet` — usually a 500. The response models traverse several such chains:
`recipe.ingredients → ingredient`, `recipe.labels → sub_category → category`, and
`planned_day.recipe`.

Some relationships already use `lazy="selectin"`, but that is a model-level default, not a
statement about which query is about to serialise what. It also loads data no response model
asked for: a plan's `PlannedRecipe` only needs a recipe's pk and name, yet loading a planned
day through the model default also fetches that recipe's ingredients. The rest of the chain
(recipe labels, a label's sub-category and category, a planned day's recipe) is not loaded
automatically at all.

## Decision

### Schemas are the boundary, ORM models are persistence

- Request and response shapes live in `meals.schemas`, split by domain and re-exported from
  `meals.schemas`. ORM models live in `meals.database.models` and are not the API or HTML
  contract.
- Request models validate and normalise input at the edge. FastAPI validates JSON bodies
  directly; the web handlers build the same models with `model_validate` from form fields;
  the seed helper parses YAML into the same models. Repositories and services accept
  validated request models rather than raw dictionaries or form values.
- Validation includes the domain rules that must not be duplicated: ingredient string
  parsing, label normalisation and uniqueness, recipe ingredient uniqueness, and the
  ingredient/instruction pairing rule. A transport that bypasses the model bypasses the
  rules, so it is a bug, not an optimisation.
- Response models use `ConfigDict(from_attributes=True)` and are built from ORM objects with
  `model_validate` in the service layer. They are what both the JSON serialiser and the htmy
  components consume; templates never receive ORM objects.
- Where the stored shape differs from the public shape, the response model adapts it with
  aliases instead of leaking the join table. `IngredientResponse.name` reads either
  `name` or `ingredient.name`, and `LabelResponse` reads
  `sub_category.category.name` and `sub_category.name`.
- Response models are also the client contract: the CLI and tests parse response JSON back
  into `PlannedRecipe` and the other response models.

### Every relationship a response model reads is eager-loaded

- The query that returns an ORM object destined for a response model must load every
  relationship that model traverses. The shared tuples in
  `src/meals/database/repository.py` are the single source of truth:
  `RECIPE_LOAD_OPTIONS` for recipes (ingredients, each ingredient, labels, each label's
  sub-category, and its category) and `PLANNED_DAY_LOAD_OPTIONS` for planned days (their
  recipe).
- `selectinload` loads collections (ingredients and labels) and `joinedload` follows the
  to-one chain from each collection row. This keeps one collection from multiplying the
  other's rows, so the queries do not need `unique()` to collapse duplicate parents. It also
  replaces the legacy `subqueryload` with the current SQLAlchemy recommendation.
- A response model that reads only part of an ORM object loads only those columns.
  `PLANNED_DAY_LOAD_OPTIONS` joins the recipe with `load_only(StoredRecipe.pk,
  StoredRecipe.name)` and applies `raiseload("*")` to the recipe path, which suppresses the
  model-level selectin relationships. A plan query therefore fetches one row and does not
  drag in ingredients or labels that `PlannedRecipe` never reads.
- Every query that can return such an object passes the matching tuple: recipe `get`,
  `get_by_name`, `get_all`, `is_like`, and the post-write reloads; plan `update` and
  `get_range`.
- Adding a relationship to a response model is not a schema-only change. It requires adding
  the load path to the relevant tuple and extending the eager-loading regression tests in
  `tests/test_database.py`.
- `test_queries_eager_load_serialised_relationships` detaches the ORM objects with
  `expunge_all()` before calling `model_validate`. A relationship that was not loaded then
  raises `DetachedInstanceError` in the test instead of becoming a `MissingGreenlet` 500 in
  production. API and web tests also exercise each endpoint with related data.
- Query-count tests lock in the cost side of the rule, which the detached-object test cannot
  see. Recipe responses must issue one select per loaded tree (recipe, ingredients, labels),
  and a plan response must issue a single select with no recipe ingredient or label query.

## Consequences

- The API, pages, and CLI share one definition of valid input and one output shape, so a rule
  cannot drift between transports.
- Changing a field or validator in `meals.schemas` affects every consumer at once. That is
  deliberate, but it makes the schema package a compatibility-sensitive shared module.
- The public JSON/HTML shape is independent of the tables: a column rename or a new join
  table does not automatically change the API.
- Eager loading makes some queries fetch more rows or issue an extra select. The cost is
  visible at the query instead of being hidden behind per-row lazy loads, and queries that do
  not serialise relationships do not pay for them. A recipe response now takes three selects;
  a plan response takes one.
- Model-level `lazy` defaults are not the contract. A query that reads only part of an object
  can override them with `raiseload`, so adding a relationship to `StoredRecipe` does not
  silently change the cost of a plan query.
- Repositories depend on request-model fields (only for typing; the runtime dependency is on
  the validated object). If storage and transport ever diverge, an explicit mapping belongs
  in the service layer rather than making the ORM model the request model.
- The detached-object test is a strong guard for known query paths, but it cannot prove that
  a brand-new query is covered. Reviewers must extend the test when adding a query that
  returns a response-model source.
- The test reports `DetachedInstanceError` while production would report `MissingGreenlet`;
  both mean the same thing — a relationship was read after the query, without being loaded —
  so the test intentionally checks the invariant rather than the exact exception type.
- Formatting validation errors is transport-specific: the API returns FastAPI's 422 body,
  while the web routes use fasthx's `error_component_selector` to render a friendly fragment.
  The models and messages are shared; only the presentation differs.

## Alternatives considered

- **Return ORM models directly from routes and repositories**: rejected because the API and
  HTML would be coupled to table and relationship structure, and every unloaded
  relationship would be a runtime 500.
- **Use ad-hoc dictionaries for responses**: rejected because there is no validation, no
  shared shape, and the API, pages, and CLI would drift.
- **Separate API DTOs and web view models**: rejected as duplication for a single
  server-rendered app; one schema package already serves JSON, HTML, and YAML.
- **Set `lazy="selectin"` on every relationship instead of per-query options**: rejected
  because it hides the query cost, loads relationships a response does not read, and still
  does not express the serialisation requirement. It is what made plan responses fetch recipe
  ingredients before the load options suppressed it.
- **Eager-load every relationship on every query**: rejected because it makes unrelated
  queries heavier and still requires a decision about which paths each response needs.
- **Serialise inside the repository**: rejected because it would make persistence responsible
  for presentation and prevent the same ORM result from being reused; the service layer is
  the conversion point.
- **Validate in the repository instead of the schema layer**: rejected because errors would
  lose their field locations and the API, forms, and YAML loader would each need their own
  pre-checks.
