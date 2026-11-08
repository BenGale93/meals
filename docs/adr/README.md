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

## Backlog

These are not written yet. They are the highest-value decisions still implicit in the
codebase, roughly in the order it is worth recording them.

| Candidate | Why it matters |
| --- | --- |
| Async SQLAlchemy repositories and service layer | Documents the repository/session pattern, dependency injection, and why the API and web layers share use cases. |
| API action conventions | Records user scoping, idempotent destructive operations, and web/JSON API parity once there are enough endpoints to justify a general rule. |
| SQLite, Alembic ownership, and backup/release strategy | Captures the single-file database, no `create_all`, stamped legacy schema, and verified-backup rules. |
| Placeholder Basic auth and the trust boundary | Records that passwords are deliberately unchecked and why that is acceptable only on the Tailscale-only, single-user deployment. |
| Structured logging, request IDs, and error responses | Explains the JSON log contract, `X-Request-ID`, and why API and page errors have different response shapes. |
| Testing strategy and the 100% branch-coverage gate | Documents the per-test transaction, savepoint override, inline snapshots, randomised order, and when browser testing is required. |
| Label model and filter semantics | Records the normalised category/sub-category/recipe-label tables and the OR-within-category, AND-across-category rule. |
| Operational CLI helpers | Explains why seeding and meal planning call the running API while the backup helper works directly on SQLite. |
| Manual deployment and blue/green candidate process | Captures the deliberate no-CI choice, on-Pi deploy, backup-first rule, and side-by-side promotion. |
