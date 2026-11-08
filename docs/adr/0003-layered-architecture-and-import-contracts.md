# 0003: Enforce a layered architecture with import-linter

- Status: Accepted
- Date: 2026-11-08

## Context

The app has two HTTP adapters over the same data: the JSON API under `/api/v1` and the
server-rendered pages under `/`. They must apply the same recipe, planner, and timings rules;
when a rule lives in a route handler, the other adapter drifts from it. The same applies to
persistence: an ORM query embedded in a route cannot be reused, optimised, or tested in
isolation.

Python does not enforce architectural boundaries. Without a check, a route can import a
repository directly, a repository can import a response model, or a core helper can import the
FastAPI app, and nothing fails until the coupling becomes expensive to unwind. A written rule
in a document is not enough, because the natural shortcut is always to add just one import.

## Decision

The code is organised into four conceptual tiers, with imports pointing downward:

1. **HTTP adapters** — `meals.api` (JSON under `/api/v1`) and `meals.web` (HTML/HTMX pages).
   They parse requests, call application services, translate domain errors into HTTP
   responses, and render or serialise the result.
2. **Application layer** — `meals.services` (shared use cases) and `meals.auth` (the current
   user dependency). This layer owns business rules, user scoping, and conversion between ORM
   objects and Pydantic response models.
3. **Persistence** — `meals.database`. Repositories own SQLAlchemy queries and return ORM
   objects; they do not know about HTTP or presentation.
4. **Shared core** — `meals.schemas`, `meals.exceptions`, `meals.constants`, `meals.settings`,
   `meals.logging_config`, `meals.middleware`, and `meals.error_handlers`. These are leaf
   modules used by several tiers; they must not depend on any tier above them.

`meals.app` is the composition root. It wires the API router, the web router, middleware, and
error handlers together, and is the only module expected to know every layer.

`meals.api` and `meals.web` are peers. Neither imports the other, and neither owns rules that
the other needs: shared behaviour belongs in `meals.services`. `meals.auth` sits in the
application layer because it reads the user repository and is consumed by both HTTP adapters;
it is not persistence and must not be imported by `meals.database`.

Two [import-linter](https://import-linter.readthedocs.io/) contracts in `pyproject.toml` make
the boundaries executable:

- **Layers** declares `meals.api | meals.web` → `meals.services | meals.auth` →
  `meals.database`. A lower layer may not import a higher one, and the two modules in a tier
  are peers.
- **Core modules do not depend on upper layers** is a forbidden contract for the shared core
  modules listed above: they may not import `meals.api`, `meals.web`, `meals.app`,
  `meals.services`, `meals.auth`, or `meals.cli`.

The contracts run as `lint-imports` in `just lint`, so `just` (the project's full gate) fails
on an upward import. The CLI helpers are not part of the layer contract: they are external
clients that talk to a running server over HTTP and only reuse `meals.schemas`.

## Consequences

- Both HTTP adapters share one implementation of each use case, so behaviour cannot silently
  diverge between the API and the page.
- Business rules are testable without FastAPI or HTML, and repository queries are testable
  without routing.
- The dependency direction is visible in the configuration and checked on every `just lint`,
  so a shortcut is rejected before review.
- New modules must be placed deliberately: a new adapter goes in `api` or `web`, a use case in
  `services`, a query in `database`, and a shared leaf in the core list. Adding a core module
  that imports upward requires changing the contract, which is an explicit architectural
  decision rather than an accident.
- `meals.auth` is coupled to the user repository, so replacing authentication with a different
  backing store is an application-layer change, not a database one.
- The layer contract names packages, not individual modules. It prevents cross-layer imports
  but does not stop a service from importing another service, or a repository from importing
  an unrelated repository; those remain review concerns.
- `meals.app` is outside the layering contract because it is the composition root, so its
  imports are not constrained. It is still forbidden to the core modules, which keeps
  infrastructure helpers from reaching back into application wiring.
- The user-creation route currently calls `UserRepo` directly because creating users is an
  API-only operation with no shared use case. If the web layer ever needs it, the rule is to
  introduce a service rather than import the route or repository.
- Import-linter includes imports made under `typing.TYPE_CHECKING` by default, so a
  type-only dependency must also point downward. The `noqa: TC001`/`TC002` markers only tell
  Ruff that the import is used solely for annotations; they are not a licence to point upward.

## Alternatives considered

- **Document the layers without enforcing them**: rejected because the web routes had already
  reimplemented domain rules once (the blank-ingredient bug was a symptom), and a convention
  nobody can run is not a constraint.
- **A single flat `meals` package**: rejected because the API and web layers need a shared
  use-case layer to prevent drift, and FastAPI's dependency injection makes that split cheap.
- **Put `meals.auth` in the database layer**: rejected because authentication is an
  application concern that uses the repository; placing it lower would invert the dependency
  and make the user repository responsible for request identity.
- **Relative imports or package-private modules instead of import-linter**: rejected because
  Python has no enforced package privacy and the checks would still need custom tests.
- **Custom import-checking tests instead of import-linter**: rejected because import-linter
  already expresses layered and forbidden contracts declaratively and reports the offending
  import chain.
