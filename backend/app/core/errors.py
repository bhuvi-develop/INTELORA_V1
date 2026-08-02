"""Error taxonomy and exception handlers.

Every failure leaves the API in the standard envelope with a stable, typed
error code. Stack traces are never returned to the client: the frontend maps
codes to user-facing copy, and the detail stays in the server log.
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.schemas.common import ApiError, envelope

logger = get_logger(__name__)

#: Starlette renamed this constant; the numeric literal is stable across both
#: versions and avoids a deprecation warning on every import.
HTTP_422_UNPROCESSABLE = 422


class ErrorCode(StrEnum):
    """Stable identifiers the frontend can branch on and localise."""

    NOT_FOUND = "RESOURCE_NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INVALID_STATE = "INVALID_STATE"
    CONFLICT = "RESOURCE_CONFLICT"
    DATA_SOURCE_UNAVAILABLE = "DATA_SOURCE_UNAVAILABLE"
    INTERNAL = "INTERNAL_ERROR"


class InteloraError(Exception):
    """Base class for all deliberately raised application errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: ErrorCode = ErrorCode.INVALID_STATE

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field

    def to_api_error(self) -> ApiError:
        return ApiError(code=self.code, message=self.message, field=self.field)


class NotFoundError(InteloraError):
    """A requested resource does not exist."""

    status_code = status.HTTP_404_NOT_FOUND
    code = ErrorCode.NOT_FOUND


class ConflictError(InteloraError):
    """The request cannot be applied to the resource's current state."""

    status_code = status.HTTP_409_CONFLICT
    code = ErrorCode.CONFLICT


class InvalidStateError(InteloraError):
    """The requested transition is not legal."""

    status_code = HTTP_422_UNPROCESSABLE
    code = ErrorCode.INVALID_STATE


class DataSourceUnavailableError(InteloraError):
    """A telemetry source the request depends on is not running."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = ErrorCode.DATA_SOURCE_UNAVAILABLE


def _error_response(status_code: int, message: str, errors: list[ApiError]) -> JSONResponse:
    body = envelope(data=None, message=message, errors=errors, ok=False)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers so every error path produces the standard envelope."""

    @app.exception_handler(InteloraError)
    async def _handle_intelora_error(_: Request, exc: InteloraError) -> JSONResponse:
        return _error_response(exc.status_code, exc.message, [exc.to_api_error()])

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            ApiError(
                code=ErrorCode.VALIDATION_FAILED,
                message=item.get("msg", "Invalid value."),
                field=".".join(str(part) for part in item.get("loc", ()) if part != "body")
                or None,
            )
            for item in exc.errors()
        ]
        return _error_response(
            HTTP_422_UNPROCESSABLE, "Request validation failed.", errors
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = (
            ErrorCode.NOT_FOUND
            if exc.status_code == status.HTTP_404_NOT_FOUND
            else ErrorCode.INVALID_STATE
        )
        message = str(exc.detail) if exc.detail else "Request could not be completed."
        return _error_response(exc.status_code, message, [ApiError(code=code, message=message)])

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Full detail to the log, a stable code to the client.
        logger.exception(
            "Unhandled exception", extra={"path": request.url.path, "method": request.method}
        )
        message = "An unexpected error occurred. The incident has been logged."
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            message,
            [ApiError(code=ErrorCode.INTERNAL, message=message)],
        )
