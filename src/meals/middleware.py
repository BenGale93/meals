"""ASGI middleware for request IDs and request logging."""

import logging
import time
import typing as t
import uuid

from starlette.datastructures import MutableHeaders

from meals.logging_config import REQUEST_ID_HEADER, request_id_var

if t.TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("meals.request")


def _request_id(scope: Scope) -> str:
    """Use a caller-supplied request ID when present, otherwise generate one."""
    headers = dict(scope.get("headers", []))
    supplied = headers.get(REQUEST_ID_HEADER.lower().encode())
    return supplied.decode("latin-1") if supplied else uuid.uuid4().hex


class RequestContextMiddleware:
    """Give every HTTP request an ID and log its method, path, status and duration."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the given ASGI application."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle an ASGI connection."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope)
        # Also expose the ID on the ASGI scope: the catch-all error handler runs
        # after this middleware has reset the context var, but still has the scope.
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code: int | None = None

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "%s %s -> %s in %sms",
                scope.get("method", "?"),
                scope.get("path", "?"),
                status_code if status_code is not None else "error",
                duration_ms,
                extra={
                    "method": scope.get("method", "?"),
                    "path": scope.get("path", "?"),
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            request_id_var.reset(token)
