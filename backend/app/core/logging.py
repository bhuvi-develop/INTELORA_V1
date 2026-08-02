"""Structured logging configuration.

INTELORA logs one JSON object per line. Machine-readable output is what makes
request, error, audit and system logs queryable once the platform is deployed
behind a log aggregator.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app.config import settings

_RESERVED_RECORD_KEYS = frozenset(
    {
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "module", "msecs",
        "message", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "thread", "threadName", "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Anything attached via `logger.info(..., extra={...})` becomes a
        # first-class field rather than being flattened into the message.
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_KEYS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging() -> None:
    """Install the JSON formatter on the root logger.

    Called once from the application lifespan, before any other subsystem
    starts, so that startup diagnostics are captured in the same format.
    """
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # uvicorn installs its own colourised handlers; route them through ours so
    # every line in the container log has the same shape.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    # SQLAlchemy is extremely verbose at INFO; it has its own echo switch.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class ContextLogger(logging.LoggerAdapter):
    """Logger that cannot be crashed by a colliding ``extra`` key.

    ``logging.makeRecord`` raises ``KeyError`` if ``extra`` contains a name the
    ``LogRecord`` already uses — ``created``, ``message``, ``module`` and a
    dozen others. It is an easy mistake to make (``extra={"created": n}`` reads
    perfectly naturally) and it turns a log line into an unhandled exception on
    whatever path emitted it, which is a spectacularly bad trade.

    Colliding keys are prefixed with ``ctx_`` instead, so the value still
    reaches the log and nothing raises.
    """

    def process(
        self, msg: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        extra = kwargs.get("extra")
        if extra:
            kwargs["extra"] = {
                (f"ctx_{key}" if key in _RESERVED_RECORD_KEYS else key): value
                for key, value in extra.items()
            }
        return msg, kwargs


def get_logger(name: str) -> ContextLogger:
    """Return a module-scoped logger with collision-safe structured context."""
    return ContextLogger(logging.getLogger(name), {})
