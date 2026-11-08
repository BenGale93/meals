# 0005: Use async repositories and a shared service layer

- Status: Accepted
- Date: 2026-11-08

## Context

The app is async. FastAPI awaits the route handlers and SQLAlchemy uses the `aiosqlite`
driver, so a synchronous session would block the event loop and database access uses
SQLAlchemy's async API. The JSON API and HTML pages need the same recipe, planner, and timings
rules. When those rules lived in route handlers, the API and pages drifted; the
blank-ingredient inconsistency was one symptom.

A request can span more than one table. Planning a meal reads a recipe and writes a planned
day; creating a recipe writes a recipe, ingredients, labels, and join rows. Those writes need
to succeed or fail together, and the HTTP layer should not have to coordinate commits. The
code also needs to be testable without starting a server or sharing a database connection
between tests.

## Decision

### Request-scoped session and transaction

- `meals.database.session` creates one async engine and one `async_sessionmaker` at import
  time. The engine enables SQLite foreign-key enforcement on every connection.
- `get_db` is a FastAPI yield dependency. It opens a session inside `session.begin()`, yields
  it, and commits when the request finishes normally or rolls back when an exception
  propagates. Repositories never commit or roll back.
- The session is created with `expire_on_commit=False`. Response models are built before the
  request ends, and tests may inspect objects after a commit; expiring every attribute on
  commit would add reloads and surprise code outside the database layer.
- FastAPI caches resolved dependencies per request, so every repository and service resolved
  for one request receives the same session. A service can therefore use two repositories and
  still get one transaction and one identity map.
- There is no separate `UnitOfWork` object; the dependency's transaction covers the request.

### Repositories

- Each aggregate has a repository (`UserRepository`, `RecipeRepository`,
  `TimingsRepository`, `PlanRepository`) in `meals.database.repository`.
- A repository is constructed with an `AsyncSession` and exposes async methods for queries and
  writes. It uses SQLAlchemy directly and is not a storage-agnostic interface.
- Repositories `flush` when they need primary keys or need to report a constraint error, but
  they do not commit. `get_db` commits or rolls back the transaction.
- Repositories return ORM objects. They do not convert to response models, raise HTTP errors,
  or know whether the caller is the API, a page, or a test.
- User-scoped reads take a `user_pk` and apply it in the query, so callers cannot forget the
  filter.
- Queries that feed response models use the eager-loading options described in
  [ADR 0004](0004-pydantic-schema-boundary-and-eager-loading.md).

### Services

- `meals.services` contains `RecipeService`, `PlanService`, and `TimingsService`. Each is
  constructed with the repositories it needs.
- A service method implements one use case. It composes repository calls, checks
  cross-repository conditions (for example, that a recipe belongs to the requesting user
  before planning it), raises domain exceptions such as `RecipeDoesNotExistError`, and
  converts ORM results into response models.
- Services take `user_pk` explicitly and do not read request state, so they can be called from
  the API, web handlers, and tests.
- The API and web layers call the same service methods. They only parse and validate their
  own input, map domain errors to transport responses, and render or serialise the result.
- User creation is an exception: it is an API-only operation with no shared use case, so
  `POST /api/v1/users` calls `UserRepository` directly. `meals.auth` also uses the user
  repository directly because it is an application-layer dependency (ADR 0003). A repository
  can be used without a service when there is no shared rule; services are for use cases, not
  a wrapper around every query.

### Dependency injection

- Each repository has a dependency factory (`get_user_repo`, `get_recipe_repo`,
  `get_timings_repo`, `get_plan_repo`) that depends on `get_db` and builds the repository. The
  module exposes `Annotated` aliases (`UserRepo`, `RecipeRepo`, `TimingRepo`, `PlanRepo`) for
  route signatures.
- Each service has a factory (`get_recipe_service`, `get_plan_service`,
  `get_timings_service`) that depends on the repository aliases, plus `Annotated` aliases
  (`RecipeServiceDep`, `PlanServiceDep`, `TimingsServiceDep`) used by the routes.
- The service classes take repositories in their constructors, so tests can pass a real
  repository backed by a test session or a recording subclass. The FastAPI `Depends` factories
  live in `services.py`, but the service methods do not call FastAPI.
- `tests/test_app.py` asserts that the `test_app` fixture builds a fresh app per test and
  overrides `get_db`. The override uses the same transaction pattern as production
  (`session.begin()` per request) and joins an outer test transaction with savepoints, so a
  request can commit without leaking data into the next test.

## Consequences

- A request that uses several repositories commits atomically. A domain error after a flush
  rolls the whole request back, so callers never see a half-written recipe or plan.
- Services can be tested without FastAPI, and repositories can be tested with a session
  alone. The HTTP layers stay thin enough that their tests mostly assert transport behaviour.
- Both adapters get identical rules; fixing a use case in one service fixes the API and the
  page at the same time.
- The repository is SQLAlchemy-specific. Changing the database would require changing
  repositories, not services.
- The session lives for the whole request, so long-running work should stay outside a request;
  the app only talks to its local SQLite database.
- `expire_on_commit=False` avoids post-commit reloads but does not refresh objects
  automatically; code that needs fresh values must query again.
- The dependency graph is visible in the route signatures. Adding a use case means adding a
  repository method and a service method; routes keep only transport concerns.
- A route may use a repository directly only when no shared use case exists. If a second
  adapter needs the same operation, move it into a service before sharing it.

## Alternatives considered

- **Synchronous SQLAlchemy sessions**: simpler in isolation, but blocks the event loop in an
  async FastAPI app and defeats the `aiosqlite` driver. Rejected.
- **A session per repository or per query**: would give each repository a different
  transaction and identity map, making multi-repository use cases non-atomic. Rejected.
- **A single global session**: unsafe across concurrent requests and impossible to roll back
  per request. Rejected.
- **Commit inside repository methods**: simple for one-table writes, but breaks atomicity for
  use cases that touch several tables and makes error handling inconsistent. Rejected.
- **Put rules in route handlers**: the original arrangement that caused API/web drift.
  Rejected.
- **Active Record methods on the ORM models**: couples persistence to domain rules, makes the
  same rule harder to reuse across transports, and complicates testing with plain objects.
  Rejected.
- **A full Unit of Work plus storage-agnostic repository interfaces**: would add abstractions
  and DTO mapping for a single-database, single-user app. The request-scoped session already
  gives the atomicity that is needed. Rejected as disproportionate.
