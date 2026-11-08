# 0006: Define user-scoped, idempotent API actions

- Status: Accepted
- Date: 2026-11-08

## Context

The JSON API and the HTML UI expose the same recipe, planner, and timings use cases. ADR 0003
and ADR 0005 moved the shared rules into services, so a route handler now parses a request,
calls a service, and maps the result. That leaves action-level rules that are easy to apply
differently in each route: which user owns a row, what happens when a delete is repeated, and
which status code a create or a conflict returns.

The cross-user planner bug made these rules visible. `POST /api/v1/planned_day` accepted a
recipe `pk` from another user because the repository wrote the value it was given. The summary
query could also count a plan stored for one user against another user. Separately, the
planner's Clear button and API clients need to clear a day that may already be empty, so a
missing row cannot be an error.

The app is deployed for one user today, but the API and tests already carry `user_pk`. The
rules below make the user boundary explicit now, so the same mistake cannot return when a
second user is added.

## Decision

### User scope

- Every data route requires `CurrentUser`, except `POST /api/v1/users` (there is no user yet)
  and `/health`. Page routes also require `CurrentUser`, so an unauthenticated page load
  returns 401 before it renders a shell whose fragments would also fail.
- The route passes the authenticated user's `pk` to the service explicitly. User-owned
  queries and writes filter by `user_pk`; the user is never read from a request body, query
  parameter, or path.
- A row owned by another user is treated as missing. Reads and updates return 404; destructive
  actions are no-ops and return the same success response as for an absent row. A clear for
  another user's day therefore returns 204 from the JSON endpoint, while the web route
  re-renders the unchanged window.
- Uniqueness is per user. Recipe names and planned days are unique for one user, not
  globally, so two users may reuse a name or plan the same day. A duplicate recipe name, or a
  timings create when the user already has a row, returns 409.
- The label taxonomy is shared, so `GET /api/v1/labels` is not user-scoped. It still requires
  authentication.

### Idempotent actions

- Clearing a planned day is idempotent. `DELETE /api/v1/planned_day` returns 204 whether the
  day was planned or not. The web Clear button posts to `/planned_day/clear`, calls the same
  `PlanService.clear`, and re-renders the window. HTML forms cannot send DELETE, so the method
  differs, but the effect is the same.
- Planning a day is an upsert keyed by `(user_pk, day)`. `POST /api/v1/planned_day` inserts or
  replaces the recipe and returns 201. Repeating the request keeps the same planned-day `pk`;
  posting a different recipe replaces the recipe.
- Timings are an upsert keyed by `user_pk`. `PATCH /timings` creates the row when it is absent
  and replaces it when present, returning 200. `POST /timings` is create-only and returns 409
  when the user already has timings.
- Status codes follow the action: 201 for a create or a plan upsert, 200 for reads and
  updates, 204 for a successful delete (including an absent day), 404 for a missing or
  cross-user row on a read or update, 409 for a per-user duplicate, and 422 for validation
  errors.
- Future destructive actions follow the same rule: deleting an absent row returns the same
  success response as deleting an existing one. Recipe deletion is not implemented yet; when
  it is added, it should use this rule.

### Shared actions

- Each shared business action is implemented by a service method. The JSON and web routes call
  that method; they do not contain SQL or a second copy of the rules. ADR 0005 defines the
  service and repository split.
- The transports differ in input and output. The API reads JSON and writes JSON; the web layer
  reads form fields and writes pages or HTMX fragments. When an action takes a payload, both
  transports build the same request model and use the same validation before the service call.
- Web-only routes handle page and fragment rendering, and some also accept form posts (such as
  `/new_recipe` and `/update_recipe/{pk}`). They call the same service methods and are not
  separate use cases.
- Adding an action means adding the schema and service method first, then the API route and/or
  web route. If both transports need the action, both call the service method.

## Consequences

- API clients can retry Clear without checking whether the day is planned, and the web button
  behaves the same way.
- Planning and timings saves converge on the last value; callers do not need separate create
  and update paths for the same natural key.
- Cross-user reads, writes, plans, summaries, and filters are rejected or ignored in the
  shared service and repository path, so a new route cannot bypass the check by forgetting a
  filter.
- Cross-user access returns 404, not 403. A caller cannot distinguish another user's row from
  a missing one.
- `POST /api/v1/planned_day` returns 201 when it replaces an existing plan, so the status does
  not distinguish insert from update. Clients use the returned `pk` and `day`. Changing that
  would need a new response contract.
- The web layer has more routes than the JSON API because it serves pages and fragments.
  Parity is measured by the shared service method, not by a one-to-one route list. Web routes
  also use form targets such as `/update_recipe/{pk}` and `/planned_day/clear`, while the JSON
  API uses resource routes.
- The rules rely on natural keys rather than idempotency keys. That is sufficient for the
  current client; a future client that retries unrelated writes would need a separate
  mechanism.
- Recipe deletion remains a TODO. The idempotent delete rule is recorded here so the new
  endpoint does not need to reopen the decision.

## Alternatives considered

- **Filter by `user_pk` only in the route handler**: rejected because the cross-user plan bug
  showed that one missed path is enough to leak or corrupt data. The service and repository
  are the shared places where the filter applies.
- **Return 403 when a row belongs to another user**: rejected because it reveals that the row
  exists. A 404 matches the result of the user-scoped query.
- **Return 404 when clearing an already-empty day**: rejected because a retry or the Clear
  button would fail for a state the caller cannot see.
- **Make the client check the plan before clearing**: rejected because it adds a round trip
  and a race between the check and the delete.
- **Use PUT for every write**: rejected because HTML forms only submit GET and POST, and
  planning a day is an upsert by natural key rather than a full resource replacement.
- **Implement the API and web actions separately**: rejected because the two layers drifted
  before (the blank-ingredient bug), and ADR 0005 already made the service the shared use
  case.
- **Add idempotency keys to every write**: rejected as unnecessary for the current client.
  The natural keys `(user_pk, day)` and `user_pk` make the retryable actions idempotent.
- **Call the JSON API from the web routes**: rejected because both layers run in the same
  process; an internal HTTP hop would add latency and another failure mode without sharing
  more logic.
