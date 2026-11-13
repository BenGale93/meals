# 0009: Use structured JSON logs and request-scoped error responses

- Status: Accepted
- Date: 2026-11-13

## Context

The app runs unattended under systemd on the Pi. Logs are read through journald, often by
piping them to `jq`. When a browser request fails, the server-side traceback and the request
that caused it need to be easy to find. Free-form text logs make that matching a parsing
exercise.

The app serves two transports: a JSON API under `/api/` and HTML pages or HTMX fragments
elsewhere. A global error handler cannot return JSON to a page or an HTML fragment to an API
client. It also cannot expose database errors or internal exception text to the caller.

The app uses Python's standard logging module. One JSON handler, a small set of fields, and a
request-scoped context variable cover the current diagnostic needs without another dependency.
The logging setup is created with the app, so development and production use the same handler
and formatter.

## Decision

### Logging

- Configure the root logger with one `StreamHandler` on stdout and `JsonFormatter`. Pytest and
  other libraries may add handlers, but the app adds its JSON handler once.
- Write one JSON object per record. The fixed fields are `timestamp` in UTC ISO 8601, `level`,
  `logger`, `request_id`, and `message`. Optional fields are `method`, `path`, `status_code`,
  `duration_ms`, and `exception` with the formatted traceback.
- Copy only the allowlisted extra fields from `_EXTRA_FIELDS`. Arbitrary values passed through
  `extra=` are not added, so the log shape stays stable for `jq` filters.
- `RequestIdFilter` adds `request_id` from `request_id_var`, or `-` outside a request. A record
  that already has an explicit `request_id` keeps it.
- `configure_logging` is idempotent. If the root logger already has a `JsonFormatter` handler,
  it only updates the level, so repeated app factories and tests do not stack handlers.
- Read `LOG_LEVEL` through `meals.settings.log_level()`. A missing or unrecognised value falls
  back to `INFO`; a typo cannot silence the logs.
- Write to stdout rather than stderr. Systemd sends both streams to journald, and stdout keeps
  the app's JSON separate from tracebacks that Python prints to stderr.
- The app does not rotate or write log files. journald owns retention and `journalctl` is the
  read path.

### Request IDs

- `RequestContextMiddleware` handles HTTP requests and passes other ASGI scopes through.
- Reuse a caller-supplied `X-Request-ID` or generate a 32-character `uuid4().hex`. A supplied
  value is correlation data, not a security token, and is not validated.
- Store the ID in `request_id_var` for the request and in `scope["state"]["request_id"]` for
  error handlers that run after the context variable is reset.
- Add `X-Request-ID` to the response start. The middleware records `method`, `path`,
  `status_code`, and `duration_ms` in the request log; if the app raises before sending a
  response, the status is logged as `error` with no status code.
- Log the request with the `meals.request` logger. Application modules use their own logger
  names, which appear in the `logger` field.
- Do not log headers, query strings, or request bodies in the request log. That keeps Basic auth
  credentials and request payloads out of the normal request line.
- The request ID is ambient through `contextvars`; services and repositories do not take it as a
  parameter just to log it.

### Error responses

- `register_exception_handlers` installs global handlers for `SQLAlchemyError`,
  `pydantic.ValidationError`, `ResponseValidationError`, and `Exception`.
- `SQLAlchemyError` means the database failed, so it returns 500 with "A database error
  occurred. Please try again." and logs at `ERROR`.
- `pydantic.ValidationError` means client input was rejected, so it returns 422 with "The
  request could not be processed." and logs at `WARNING`.
- `ResponseValidationError` means the app produced a malformed response, so it returns 500 with
  "An unexpected error occurred. Please try again." and logs at `ERROR`.
- `Exception` returns the same 500 message and logs at `ERROR`.
- Every handler logs the traceback with the request ID, then returns a response with the
  `X-Request-ID` header.
- Choose the response shape from the path. Paths under `/api/` get
  `{"detail": ..., "request_id": ...}`. Other paths get a small HTML fragment with the message
  and `Reference: <id>`, which HTMX can swap into the page.
- The user-facing detail is a fixed message. The exception text and traceback stay in the log.
- Expected `HTTPException` responses such as 401, 404, and 409 keep FastAPI's default handling.
  These handlers are for database failures and exceptions that escape a route; the per-request
  log still records their status.
- FastAPI request parsing runs before the route and keeps FastAPI's default 422 response. The
  custom `ValidationError` path covers validation errors raised inside route or service code.
- `HTTPException` and request parsing errors do not use the custom error shape. The API and page
  response distinction above applies to the exceptions handled here.

## Consequences

- An unhandled failure produces two log records: the `meals.errors` record with the traceback
  and the `meals.request` completion record with method, path, status, and duration. They share
  the request ID.
- On custom error responses, the `X-Request-ID` header and the API response body both carry the
  ID. The HTML error fragment carries it as a reference, so a user can quote it when reporting
  a failure.
- Every HTTP request is logged, including `/health`. There is no sampling. At one user's traffic
  the volume is small, and the health line is useful during deploys.
- The JSON schema is deliberately narrow. A new diagnostic field needs an edit to
  `_EXTRA_FIELDS`; arbitrary `extra=` data is dropped rather than silently changing the format.
- The logging setup does not depend on request state. Startup logs use `-` as the request ID.
- A caller can choose the request ID. It is useful when a proxy or client already assigned one,
  but it cannot be used to identify or trust a caller.
- FastAPI's request-validation 422 and the custom 422 have different bodies. The former keeps
  the framework payload and has no custom `request_id` field; the latter has the fixed detail
  and request ID.
- Unhandled error details are not returned to clients. Diagnosing a 500 requires the request ID
  and access to the server log.

## Alternatives considered

- **Plain text logs**: rejected because filtering by request ID, status, path, or duration would
  require parsing each line. JSON gives journald and `jq` stable fields.
- **`structlog` or `loguru`**: rejected because the standard library already provides the
  handler, formatter, filter, and context variable used here. Another dependency would add
  configuration without a current need.
- **Log to a rotating file**: rejected because systemd already captures stdout in journald and
  handles retention. A file would add permissions and rotation to the app.
- **Log to stderr**: rejected because Python and other tools also write tracebacks there.
  stdout keeps the app's JSON lines separate.
- **Always generate a request ID**: rejected because reusing a caller's ID lets a proxy or
  client correlate its own logs with the app's. The supplied value is not trusted for anything
  except correlation.
- **Pass the request ID through every service and repository call**: rejected because it would
  add a logging parameter to the application and persistence layers. The context variable keeps
  the ID available to the logging filter without changing those APIs.
- **Use FastAPI's default error responses for every exception**: rejected because page clients
  would receive FastAPI's JSON or plain-text default instead of an HTML fragment, API clients
  would not get a request ID in the body, and unhandled exceptions would not produce the
  intended log record.
- **Return the exception text to the client**: rejected because database errors and internal
  tracebacks can expose implementation details or data.
- **Choose API versus page responses from the `Accept` header**: rejected because the `/api/`
  prefix already separates the two transports and HTMX requests do not always send a
  distinguishing `Accept` value.
- **Use a tracing system such as OpenTelemetry**: rejected for one service on one host. Request
  IDs and structured logs cover the current diagnosis; tracing can be added if the deployment
  grows.
