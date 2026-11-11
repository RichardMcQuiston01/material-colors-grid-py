"""Result types for fallible operations.

Expected failures are returned as ``Err`` values instead of being raised, so
callers must check the result before using the value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    """A successful result carrying ``value``."""

    value: T


@dataclass(frozen=True, slots=True)
class Err:
    """A failed result carrying a descriptive ``error`` message."""

    error: str


Result = Ok[T] | Err
