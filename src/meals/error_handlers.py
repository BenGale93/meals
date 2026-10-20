"""Global exception handlers.

These are the last line of defence: bugs and database failures still produce a
clean response (and a log line with a request ID) instead of a bare traceback.
"""

import logging
import typing as t

from fastapi import FastAPI, Request, status
from fastapi.exceptions import ResponseValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from meals.logging_config import REQUEST_ID_HEADER, request_id_var

logger = logging.getLogger("meals.errors")

_DATABASE_ERROR = "A database error occurred. Please try again."
_INVALID_REQUEST = "The request could not be processed."
_UNEXPECTED_ERROR = "An unexpected error occurred. Please try again."


def _request_id(request: Request) -> str:
    """Return the request ID assigned by the middleware, if there is one."""
    return t.cast("str", getattr(request.state, "request_id", request_id_var.get() or "unknown"))


def _is_api(request: Request) -> bool:
    """Return whether the request came from the JSON API rather than a page."""
    return request.url.path.startswith("/api/")


def _error_response(request: Request, status_code: int, detail: str) -> Response:
    """Build a response matching the transport, carrying the request ID."""
    request_id = _request_id(request)
    headers = {REQUEST_ID_HEADER: request_id}
    if _is_api(request):
        return JSONResponse(
            {"detail": detail, "request_id": request_id},
            status_code=status_code,
            headers=headers,
        )
    return HTMLResponse(
        f'<div class="p-4 bg-red-50 border border-red-200 text-red-800 rounded-lg">'
        f"<p>{detail}</p>"
        f'<p class="text-sm mt-1">Reference: {request_id}</p>'
        f"</div>",
        status_code=status_code,
        headers=headers,
    )


def _log_error(request: Request, message: str, exc: Exception, *, level: int) -> None:
    """Log an exception with its traceback and the current request ID."""
    logger.log(
        level,
        "%s %s %s: %s",
        message,
        request.method,
        request.url.path,
        exc,
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={"request_id": _request_id(request)},
    )


async def handle_database_error(request: Request, exc: Exception) -> Response:
    """Log a database failure and return a generic 500."""
    _log_error(request, "Database error handling", exc, level=logging.ERROR)
    return _error_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, _DATABASE_ERROR)


async def handle_validation_error(request: Request, exc: Exception) -> Response:
    """Log a validation failure escaping a route.

    A ``ValidationError`` usually means client input was rejected, so it becomes
    a 422; a ``ResponseValidationError`` means our own response was malformed, so
    it stays a 500.
    """
    if isinstance(exc, ResponseValidationError):
        _log_error(request, "Response validation error handling", exc, level=logging.ERROR)
        return _error_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, _UNEXPECTED_ERROR)
    _log_error(request, "Validation error handling", exc, level=logging.WARNING)
    return _error_response(request, status.HTTP_422_UNPROCESSABLE_CONTENT, _INVALID_REQUEST)


async def handle_unexpected_error(request: Request, exc: Exception) -> Response:
    """Log an unhandled exception and return a generic 500."""
    _log_error(request, "Unhandled error handling", exc, level=logging.ERROR)
    return _error_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, _UNEXPECTED_ERROR)


def register_exception_handlers(app: FastAPI) -> None:
    """Install the global exception handlers on the application."""
    app.add_exception_handler(SQLAlchemyError, handle_database_error)
    app.add_exception_handler(ValidationError, handle_validation_error)
    app.add_exception_handler(ResponseValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
