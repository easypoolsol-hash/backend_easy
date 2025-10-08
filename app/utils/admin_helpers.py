"""Small helpers for Django admin UI helpers used across admin modules.

Provide a typed decorator to set attributes like ``short_description`` and
``boolean`` on admin display functions in a way that's friendly to mypy.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])


def admin_display(
    short_description: str | None = None,
    boolean: bool = False,
) -> Callable[[F], F]:
    """Decorator to set Django admin display attributes on a function.

    Example:
        @admin_display("Name")
        def get_name(self, obj):
            return obj.name

    Uses a single, explicit cast to ``Any`` when assigning attributes so the
    type checker understands the deliberate attr assignment.
    """

    def deco(func: F) -> F:
        if short_description is not None:
            cast(Any, func).short_description = short_description
        if boolean:
            cast(Any, func).boolean = True
        return func

    return deco
