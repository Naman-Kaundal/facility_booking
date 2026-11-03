"""Consistent API error format (LLD §11.8).

Every error response has the shape::

    {"error": {"code": "SOME_CODE", "message": "Human readable", "details": {}}}
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Raise from services/routes to return a structured error."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Only expose location/message/type; never echo internals.
        fields = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg", ""), "type": err.get("type", "")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "One or more fields are invalid.", {"fields": fields}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(status_code=exc.status_code, content=error_body(code, message))

    @app.exception_handler(OperationalError)
    async def _database_unavailable(_: Request, exc: OperationalError) -> JSONResponse:
        logger.warning("Database unavailable: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=503,
            content=error_body("DATABASE_UNAVAILABLE", "The database is not reachable. Please try again shortly."),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "An unexpected error occurred."),
        )
