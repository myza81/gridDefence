"""Shared pagination contract.

Per CLAUDE.md A9, every collection endpoint defines a pagination convention.
This is the one shared shape every module's list endpoints reuse, rather
than each module inventing its own.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    """Query parameters for a paginated request."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class Page(BaseModel, Generic[T]):
    """A single page of results, with enough metadata to fetch the next one."""

    items: list[T]
    page: int
    page_size: int
    total: int
