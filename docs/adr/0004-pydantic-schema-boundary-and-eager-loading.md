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

Some relationships already use `lazy="selectin"`, but that is a model-level default and does
not describe which query will serialise which relationship. It also loads data no response
model asked for: a plan's `PlannedRecipe` only needs a recipe's pk and name, yet loading a
planned day through the model default also fetches that recipe's ingredients. The rest of the chain
(recipe labels, a label's sub-category and category, a planned day's recipe) is not loaded
automatically at all.

## Decision

### Schemas and ORM models

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
  rules; that is a bug.
- Response models use `ConfigDict(from_attributes=True)` and are built from ORM objects with
  `model_validate` in the service layer. They are what both the JSON serialiser and the htmy
  components consume; templates never receive ORM objects.
- Where the stored shape differs from the public shape, the response model adapts it with
  aliases instead of leaking the join table. `IngredientResponse.name` reads either
  `name` or `ingredient.name`, and `LabelResponse` reads
  `sub_category.category.name` and `sub_category.name`.
- Response models are also the client contract: the CLI and tests parse response JSON back
  into `PlannedRecipe` and the other response models.

### Eager loading

- The query that returns an ORM object destined for a response model must load every
  relationship that model traverses. The shared tuples in
  `src/meals/database/repository.py` define the load options:
  `RECIPE_LOAD_OPTIONS` for recipes (ingredients, each ingredient, labels, each label's
  sub-category, and its category) and `PLANNED_DAY_LOAD_OPTIONS` for planned days (their
  recipe).
- `selectinload` loads collections (ingredients and labels) and `joinedload` follows the
  to-one chain from each collection row. This prevents one collection from multiplying the
  other's rows and avoids duplicate parents. It also replaces the legacy `subqueryload` with
  the current SQLAlchemy recommendation.
- A response model that uses only some columns loads only those columns.
  `PLANNED_DAY_LOAD_OPTIONS` joins the recipe with `load_only(StoredRecipe.pk,
  StoredRecipe.name)` and applies `raiseload("*")` to the recipe path, which suppresses the
  model-level selectin relationships. A plan query therefore fetches one row and does not
  load ingredients or labels that `PlannedRecipe` never reads.
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
- Query-count tests check the cost, which the detached-object test cannot. Recipe responses
  must issue one select per loaded tree (recipe, ingredients, labels), and a plan response
  must issue a single select with no recipe ingredient or label query.

## Consequences

- The API, pages, and CLI share one definition of valid input and one output shape, so a rule
  cannot drift between transports.
- Changing a field or validator in `meals.schemas` affects every consumer at once. That is
  expected, but it makes the schema package a compatibility-sensitive shared module.
- The public JSON/HTML shape is independent of the tables: a column rename or a new join
  table does not automatically change the API.
- Eager loading makes some queries fetch more rows or issue an extra select. The cost is
  visible in the query instead of being hidden in per-row lazy loads, and queries that do not
  serialise relationships do not load them. A recipe response now takes three selects; a plan
  response takes one.
- Model-level `lazy` settings are defaults; each query still decides what to load. A query
  that uses only part of an object can override them with `raiseload`, so a new
  `StoredRecipe` relationship does not silently change the cost of a plan query.
- Repositories depend on request-model fields for typing, but the runtime dependency is on the
  validated object. If storage and transport ever diverge, an explicit mapping belongs in the
  service layer rather than making the ORM model the request model.
- The detached-object test covers known query paths, but not a new query. Reviewers must
  extend it when adding a query that returns a response-model source.
- The test raises `DetachedInstanceError` where production raises `MissingGreenlet`; both
  mean a relationship was read after the query without being loaded. The test checks that
  invariant, not the exception type.
- Validation errors are presented differently by transport: the API returns FastAPI's 422
  body, while the web routes use fasthx's `error_component_selector` to render an HTML
  fragment. The models and messages are shared; only the presentation differs.

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
  does not express the serialisation requirement. It caused plan responses to fetch recipe
  ingredients before the load options suppressed them.
- **Eager-load every relationship on every query**: rejected because it makes unrelated
  queries heavier and still requires a decision about which paths each response needs.
- **Serialise inside the repository**: rejected because it would make persistence responsible
  for presentation and prevent the same ORM result from being reused; the service layer is
  the conversion point.
- **Validate in the repository instead of the schema layer**: rejected because errors would
  lose their field locations and the API, forms, and YAML loader would each need their own
  pre-checks.
