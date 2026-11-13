# 0010: Test against real SQLite and gate on 100% branch coverage

- Status: Accepted
- Date: 2026-11-13

## Context

The test suite is the release gate before `just deploy`. There is no CI and the Pi does not run
tests. The suite has to catch SQLAlchemy query and eager-loading mistakes, schema behaviour,
HTTP and HTMX response shapes, and CLI calls without starting a live server.

Mocked repositories would miss the SQL and async-loading failures that have caused production
500s. A separate database server would add a service the app does not use. Browser automation
would add a second runtime for a small application whose JavaScript is limited to HTMX and
Alpine interactions.

## Decision

### Test layers

- Test every layer through its public interface: repositories and services against real SQLite,
  the JSON API through `httpx.AsyncClient` with `ASGITransport`, pages through their rendered
  HTML, and CLI helpers through `CliRunner` and an ASGI client.
- Organise tests by domain under `tests/api/` and `tests/web/`, with core modules at the top
  level. Share users, recipes, timings, and clients through `tests/conftest.py` fixtures.
- Start bug fixes with a failing test that reproduces the bug. Add the test to the domain file,
  not a per-bug file.
- Use `time-machine` for date-dependent behaviour and `inline-snapshot` where an exact API
  payload is easier to review than field-by-field assertions.

### Database isolation

- The root `conftest.py` sets `DATABASE_URL` to an in-memory database before `meals` is
  imported, so the module-level engine cannot open the configured database.
- Give each test a `tmp_path` SQLite file and a fresh engine, then build the schema with
  `Base.metadata.create_all`.
- Hold one outer transaction open for the test and roll it back at the end. Force `BEGIN` before
  the test body because SQLite otherwise defers it until the first write, which would let a
  savepoint commit on its own.
- The test session and each request session join the outer transaction with
  `join_transaction_mode="create_savepoint"`. Request commits are visible to the test session
  but not to another connection, and they disappear when the outer transaction rolls back.
- Build the app per test and override `get_db` on that instance, so dependency overrides cannot
  leak into the module-global app. The `client`, `bad_client`, and `user_two_client` fixtures
  create their users through the API.

### Coverage and order

- `just test` runs `pytest tests/` and then `coverage report --fail-under=100`. Coverage is
  branch coverage over `src/`.
- Coverage exclusions live in `[tool.coverage.report]` (`TYPE_CHECKING`, overloads,
  abstract methods, `__repr__`) and `main.py` is omitted. New code must otherwise be covered.
- Keep `pytest-randomly` enabled. Tests must not depend on file or declaration order; use
  `-p no:randomly` only to debug an ordering failure.
- Run `just` locally before committing. There is no CI and no test run on the Pi.

### Assertions and browser checks

- Prefer behaviour assertions: status codes, selected markup, parsed HTML, database state, and
  exact schemas. Coverage is a floor; tests still need to assert the result.
- HTML tests use focused assertions and helpers rather than whole-page snapshots. A shared page
  shell change should not break every page test.
- Markup tests do not execute JavaScript. After changing HTMX or Alpine behaviour, exercise the
  flow in a browser and check the console; add a raw script assertion where that catches a
  regression. The suite has no headless browser.

## Consequences

- The suite exercises the same SQLite engine and SQLAlchemy behaviour as production, including
  eager loading, constraints, and cascades.
- Tests are isolated without cleanup code or ordering rules. The savepoint arrangement makes
  request commits observable to the test while the outer rollback keeps the file disposable.
- The transaction and savepoint setup is more complex than a single session, and the forced
  `BEGIN` is easy to remove by accident. Database tests cover the isolation and the forced
  `BEGIN`.
- The 100% branch gate exposes untested branches, but it can encourage low-value tests around
  trivial branches. Assertions still decide whether a test is useful.
- Tests build the schema from metadata, not by running Alembic. Migrations are exercised by the
  deploy and candidate paths, not by the suite.
- Random order catches hidden coupling. A failing order needs the seed or `-p no:randomly` to
  reproduce.
- JavaScript behaviour is covered only by manual browser checks. A JavaScript regression can
  pass the test suite.
- No CI means the local `just` run is the only automated gate.

## Alternatives considered

- **Mock repositories and services in API tests**: rejected because the tests would not catch
  SQL, transaction, constraint, or async eager-loading failures.
- **Share one database or session across tests**: rejected because writes and dependency
  overrides would leak between tests and make the result depend on order.
- **Use an in-memory SQLite database per test**: rejected because the isolation check needs a
  second connection to see the same database, and `:memory:` gives each connection its own.
  A per-test file avoids shared-cache setup.
- **Lower the coverage threshold**: rejected for a small codebase with no CI; 100% branch
  coverage keeps untested paths visible.
- **Snapshot whole HTML pages**: rejected because shared-shell changes would create large
  review diffs and unrelated failures. Focused assertions and helpers are cheaper to maintain.
- **Add headless browser tests**: rejected for the current JavaScript surface. A browser
  dependency and its flakiness would outweigh the coverage; manual checks are the current
  trade-off.
- **Run tests in fixed order**: rejected because random order exposes state leaks and hidden
  fixture coupling.
- **Add CI**: rejected for this solo, single-host deployment. The local `just` gate and the
  candidate deploy cover the release.
