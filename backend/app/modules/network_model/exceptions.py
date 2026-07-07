"""Network Model business errors (CLAUDE.md A9 — structured, not ad hoc)."""

from __future__ import annotations

from app.shared.exceptions import AppError, NotFoundError

__all__ = ["AppError", "NotFoundError", "SubstationNotFoundError"]


class SubstationNotFoundError(NotFoundError):
    def __init__(self, substation_id: object) -> None:
        super().__init__(f"Substation {substation_id} not found")
