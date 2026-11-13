# Architecture Decision Records

This folder records the durable architectural decisions behind the meals app. An ADR
explains **why** a choice was made, what it costs, and what was rejected, so future
changes do not have to rediscover the reasoning from the code or commit history.

## When to add an ADR

Add one when a decision:

- changes the shape of the system (layers, boundaries, data ownership, deployment);
- is expensive or disruptive to reverse;
- will surprise someone reading the code without context;
- settles a trade-off that is likely to be revisited.

Small implementation details belong in code comments, docstrings, or the commit message.
Bug fixes and routine features do not need an ADR unless they establish a new rule.

## Format

Each ADR is numbered, immutable once accepted, and uses this shape:

```markdown
# NNNN: Short decision title

- Status: Proposed | Accepted | Superseded by ADR-NNNN | Deprecated
- Date: YYYY-MM-DD

## Context

What problem or forces led to the decision?

## Decision

What we chose, stated in the present tense.

## Consequences

What becomes easier, what becomes harder, and what follow-up work remains.

## Alternatives considered

- **Option**: why it was not chosen.
```

If a decision changes, add a new ADR that supersedes the old one rather than rewriting
history. Keep the old file and update its status.

## Index

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-planner-window-and-url-contract.md) | Define the planner window and URL contract | Accepted |
| [0002](0002-server-rendered-ui-and-htmx-navigation.md) | Use server-rendered HTML with HTMX navigation | Accepted |
| [0003](0003-layered-architecture-and-import-contracts.md) | Enforce a layered architecture with import-linter | Accepted |
| [0004](0004-pydantic-schema-boundary-and-eager-loading.md) | Use Pydantic schemas as the boundary and eager-load response relationships | Accepted |
| [0005](0005-async-repositories-and-service-layer.md) | Use async repositories and a shared service layer | Accepted |
| [0006](0006-user-scoped-idempotent-api-actions.md) | Define user-scoped, idempotent API actions | Accepted |
| [0007](0007-sqlite-alembic-and-backup-first-releases.md) | Run SQLite with an Alembic-managed schema and backup-first releases | Accepted |
| [0008](0008-placeholder-basic-auth-and-trust-boundary.md) | Use placeholder Basic auth behind a private network boundary | Accepted |
| [0009](0009-structured-logging-request-ids-and-error-responses.md) | Use structured JSON logs and request-scoped error responses | Accepted |

## Backlog

These are not written yet. They are the highest-value decisions still implicit in the
codebase, roughly in the order it is worth recording them.

| Candidate | Why it matters |
| --- | --- |
| Testing strategy and the 100% branch-coverage gate | Documents the per-test transaction, savepoint override, inline snapshots, randomised order, and when browser testing is required. |
| Label model and filter semantics | Records the normalised category/sub-category/recipe-label tables and the OR-within-category, AND-across-category rule. |
| Operational CLI helpers | Explains why seeding and meal planning call the running API while the backup helper works directly on SQLite. |
