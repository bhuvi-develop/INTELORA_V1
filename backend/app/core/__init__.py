"""Cross-cutting concerns — logging, error taxonomy and application lifespan."""

from app.core.errors import (
    ConflictError,
    DataSourceUnavailableError,
    ErrorCode,
    InteloraError,
    InvalidStateError,
    NotFoundError,
    register_exception_handlers,
)
from app.core.logging import configure_logging, get_logger

__all__ = [
    "ConflictError",
    "DataSourceUnavailableError",
    "ErrorCode",
    "InteloraError",
    "InvalidStateError",
    "NotFoundError",
    "configure_logging",
    "get_logger",
    "register_exception_handlers",
]
