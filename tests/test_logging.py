import json
import logging
import typing as t

import pytest
from fastapi import FastAPI
from fastapi.exceptions import ResponseValidationError
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from meals.app import create_app
from meals.error_handlers import (
    handle_database_error,
    handle_unexpected_error,
    handle_validation_error,
    register_exception_handlers,
)
from meals.logging_config import (
    REQUEST_ID_HEADER,
    JsonFormatter,
    RequestIdFilter,
    configure_logging,
    request_id_var,
)
from meals.middleware import RequestContextMiddleware
from meals.schemas import CreateUserRequest
from meals.settings import log_level

if t.TYPE_CHECKING:
    from starlette.types import Message, Scope, Send


async def _receive() -> Message:
    return {"type": "http.request"}


async def _send(_: Message) -> None:
    """Discard outgoing messages."""


def build_error_app(exc: Exception) -> FastAPI:
    """Build a small app whose routes raise the given exception."""
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom_page() -> None:
        raise exc

    @app.get("/api/boom")
    async def boom_api() -> None:
        raise exc

    return app


def validation_error() -> ValidationError:
    """Build a real pydantic validation error."""
    with pytest.raises(ValidationError) as exc_info:
        CreateUserRequest.model_validate({})
    return exc_info.value


def raise_value_error() -> None:
    """Raise a ValueError so a test can capture its traceback."""
    msg = "bad"
    raise ValueError(msg)


def http_scope(**overrides: t.Any) -> Scope:
    """Build a minimal HTTP ASGI scope."""
    scope: dict[str, t.Any] = {"type": "http", "method": "GET", "path": "/", "headers": []}
    scope.update(overrides)
    return t.cast("Scope", scope)


class TestRequestIdMiddleware:
    async def test_generates_a_request_id(self, client: AsyncClient):
        response = await client.get("/health")

        request_id = response.headers[REQUEST_ID_HEADER]

        assert len(request_id) == 32
        int(request_id, 16)

    async def test_reuses_a_supplied_request_id(self, client: AsyncClient):
        response = await client.get("/health", headers={REQUEST_ID_HEADER: "req-123"})

        assert response.headers[REQUEST_ID_HEADER] == "req-123"

    async def test_logs_the_request(self, client: AsyncClient, caplog: pytest.LogCaptureFixture):
        with caplog.at_level(logging.INFO, logger="meals.request"):
            response = await client.get("/health", headers={REQUEST_ID_HEADER: "log-me"})

        assert response.status_code == 200

        record = next(record for record in caplog.records if record.name == "meals.request")

        assert record.getMessage().startswith("GET /health -> 200 in ")
        assert getattr(record, "request_id") == "log-me"
        assert getattr(record, "method") == "GET"
        assert getattr(record, "path") == "/health"
        assert getattr(record, "status_code") == 200
        assert isinstance(getattr(record, "duration_ms"), float)

    async def test_passes_through_non_http_connections(self):
        seen: list[str] = []

        async def app(scope: Scope, _receive: t.Any, _send: t.Any) -> None:
            seen.append(scope["type"])

        await RequestContextMiddleware(app)(t.cast("Scope", {"type": "lifespan"}), _receive, _send)

        assert seen == ["lifespan"]

    async def test_logs_error_when_the_app_raises(self, caplog: pytest.LogCaptureFixture):
        async def app(_scope: Scope, _receive: t.Any, _send: t.Any) -> None:
            msg = "boom"
            raise RuntimeError(msg)

        with caplog.at_level(logging.INFO, logger="meals.request"), pytest.raises(RuntimeError):
            await RequestContextMiddleware(app)(http_scope(path="/boom"), _receive, _send)

        record = next(record for record in caplog.records if record.name == "meals.request")

        assert record.getMessage().startswith("GET /boom -> error in ")
        assert getattr(record, "status_code") is None

    async def test_ignores_messages_that_are_not_the_response_start(self):
        sent: list[Message] = []

        async def app(_scope: Scope, _receive: t.Any, send: Send) -> None:
            await send({"type": "http.response.body", "body": b""})

        async def send(message: Message) -> None:
            sent.append(message)

        await RequestContextMiddleware(app)(http_scope(), _receive, send)

        assert sent == [{"type": "http.response.body", "body": b""}]


class TestLoggingConfiguration:
    def test_log_level_defaults_to_info(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        assert log_level() == logging.INFO

    def test_log_level_reads_the_environment(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LOG_LEVEL", "debug")

        assert log_level() == logging.DEBUG

    def test_log_level_falls_back_for_unknown_names(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LOG_LEVEL", "not-a-level")

        assert log_level() == logging.INFO

    def test_configure_logging_adds_one_json_handler(self):
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        original_level = root.level
        try:
            root.handlers = [handler for handler in root.handlers if not isinstance(handler.formatter, JsonFormatter)]

            configure_logging()
            configure_logging()

            json_handlers = [handler for handler in root.handlers if isinstance(handler.formatter, JsonFormatter)]

            assert len(json_handlers) == 1
            assert any(isinstance(f, RequestIdFilter) for f in json_handlers[0].filters)
            assert root.level == log_level()
        finally:
            root.handlers = original_handlers
            root.setLevel(original_level)

    def test_formatter_includes_context_and_extra_fields(self):
        record = logging.LogRecord("meals.test", logging.INFO, __file__, 1, "hello %s", ("world",), None)
        setattr(record, "request_id", "req-1")
        setattr(record, "method", "GET")

        payload = json.loads(JsonFormatter().format(record))

        assert payload["level"] == "INFO"
        assert payload["logger"] == "meals.test"
        assert payload["request_id"] == "req-1"
        assert payload["message"] == "hello world"
        assert payload["method"] == "GET"
        assert "path" not in payload
        assert "timestamp" in payload
        assert "exception" not in payload

    def test_formatter_includes_the_traceback(self):
        with pytest.raises(ValueError, match="bad") as raised:
            raise_value_error()

        exc = raised.value
        record = logging.LogRecord(
            "meals.test", logging.ERROR, __file__, 1, "boom", (), (type(exc), exc, exc.__traceback__)
        )

        payload = json.loads(JsonFormatter().format(record))

        assert "ValueError: bad" in t.cast("str", payload["exception"])

    def test_filter_uses_the_current_request_id(self):
        record = logging.LogRecord("meals.test", logging.INFO, __file__, 1, "hello", (), None)
        token = request_id_var.set("ctx-1")
        try:
            assert RequestIdFilter().filter(record) is True
        finally:
            request_id_var.reset(token)

        assert getattr(record, "request_id") == "ctx-1"

    def test_filter_defaults_to_a_dash(self):
        record = logging.LogRecord("meals.test", logging.INFO, __file__, 1, "hello", (), None)

        assert RequestIdFilter().filter(record) is True
        assert getattr(record, "request_id") == "-"

    def test_filter_keeps_an_explicit_request_id(self):
        record = logging.LogRecord("meals.test", logging.INFO, __file__, 1, "hello", (), None)
        setattr(record, "request_id", "explicit")

        assert RequestIdFilter().filter(record) is True
        assert getattr(record, "request_id") == "explicit"


class TestExceptionHandlers:
    def test_handlers_are_registered(self):
        app = create_app()

        assert app.exception_handlers[SQLAlchemyError] is handle_database_error
        assert app.exception_handlers[ValidationError] is handle_validation_error
        assert app.exception_handlers[ResponseValidationError] is handle_validation_error
        assert app.exception_handlers[Exception] is handle_unexpected_error

    @pytest.mark.parametrize(
        ("make_exc", "path", "status_code", "message", "content_type"),
        [
            (lambda: SQLAlchemyError("boom"), "/api/boom", 500, "database error", "application/json"),
            (lambda: SQLAlchemyError("boom"), "/boom", 500, "database error", "text/html"),
            (validation_error, "/api/boom", 422, "could not be processed", "application/json"),
            (validation_error, "/boom", 422, "could not be processed", "text/html"),
            (
                lambda: ResponseValidationError([], body={}),
                "/api/boom",
                500,
                "unexpected error",
                "application/json",
            ),
            (lambda: ResponseValidationError([], body={}), "/boom", 500, "unexpected error", "text/html"),
            (lambda: RuntimeError("boom"), "/api/boom", 500, "unexpected error", "application/json"),
            (lambda: RuntimeError("boom"), "/boom", 500, "unexpected error", "text/html"),
        ],
    )
    async def test_returns_a_clean_response(  # noqa: PLR0913, PLR0917
        self,
        make_exc: t.Callable[[], Exception],
        path: str,
        status_code: int,
        message: str,
        content_type: str,
        caplog: pytest.LogCaptureFixture,
    ):
        transport = ASGITransport(app=build_error_app(make_exc()), raise_app_exceptions=False)

        with caplog.at_level(logging.WARNING, logger="meals.errors"):
            async with AsyncClient(
                transport=transport, base_url="http://test", headers={REQUEST_ID_HEADER: "req-123"}
            ) as client:
                response = await client.get(path)

        assert response.status_code == status_code
        assert response.headers[REQUEST_ID_HEADER] == "req-123"
        assert response.headers["content-type"].startswith(content_type)
        if content_type == "application/json":
            body = response.json()
            assert body["request_id"] == "req-123"
            assert message in str(body["detail"]).lower()
        else:
            assert message in response.text.lower()
            assert "Reference: req-123" in response.text

        record = next(record for record in caplog.records if record.name == "meals.errors")
        assert getattr(record, "request_id") == "req-123"
        assert record.exc_info is not None
