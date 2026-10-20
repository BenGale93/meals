"""Structured logging and request-scoped logging context.

The app logs one JSON object per line to stdout, which systemd captures in
journald. Every record carries the current request's ID so a browser response
(its ``X-Request-ID`` header) can be matched to the log lines it produced.
"""

import json
import logging
import sys
import typing as t
from contextvars import ContextVar
from datetime import UTC, datetime

from meals.settings import log_level

REQUEST_ID_HEADER = "X-Request-ID"

# Extra fields a log call may pass via ``extra=``; all are rendered as top-level
# JSON keys so the output stays easy to filter with ``jq``.
_EXTRA_FIELDS = ("method", "path", "status_code", "duration_ms")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Add the current request ID to every log record."""

    @t.override
    def filter(self, record: logging.LogRecord) -> bool:
        """Attach ``request_id``, defaulting to ``-`` outside a request."""
        if getattr(record, "request_id", None) is None:
            record.request_id = request_id_var.get() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """Render a log record as a single JSON object."""

    @t.override
    def format(self, record: logging.LogRecord) -> str:
        """Return the record serialised as one line of JSON."""
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            if (value := getattr(record, field, None)) is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    """Configure the root logger once, writing JSON lines to stdout.

    ``StreamHandler`` defaults to stderr, but systemd sends both streams to
    journald; stdout keeps the app's lines separate from tracebacks printed by
    Python itself and is what uvicorn expects for its own logs.
    """
    root = logging.getLogger()
    if not any(isinstance(handler.formatter, JsonFormatter) for handler in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler.addFilter(RequestIdFilter())
        root.addHandler(handler)
    root.setLevel(log_level())
