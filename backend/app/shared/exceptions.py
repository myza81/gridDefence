"""Shared application exceptions.

Per CLAUDE.md A9, every non-success API response is a structured error, not a
bare stack trace or an ad hoc dict. Business modules raise these (or their own
subclasses) from the service layer; routers stay thin and never construct
error responses inline (CLAUDE.md §14).
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all application-raised errors.

    Not tied to any transport (HTTP, etc.) — a FastAPI exception handler
    maps this to a structured response once real endpoints exist.
    """

    def __init__(self, message: str, *, code: str = "app_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class NotFoundError(AppError):
    """Raised when a requested entity does not exist."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, code="not_found")


class ValidationAppError(AppError):
    """Raised for business-rule validation failures (CLAUDE.md A11).

    Distinct from Pydantic's own request-shape validation, which FastAPI
    already handles — this is for domain/business rule violations raised
    from the service layer.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, code="validation_error")
