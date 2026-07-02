"""Logging configuration.

Per CLAUDE.md §16: logging is operational diagnostics (performance, errors,
infrastructure events) and is a distinct concern from engineering audit trails.
Audit logging is owned by each business module once it exists — this module
only sets up process-level diagnostic logging.
"""

import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure root logging once, at application startup."""
    settings = get_settings()
    level = logging.DEBUG if settings.is_development else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
