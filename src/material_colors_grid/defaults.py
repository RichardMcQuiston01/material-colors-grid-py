"""Factories for documents, categories, and colors with generated ids."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from material_colors_grid.models import Category, Color, ProjectDocument

DEFAULT_CATEGORY_NAME = "Default"


def _generate_id() -> str:
    """Return a new random identifier (a UUID4 string)."""
    return str(uuid.uuid4())


def create_color(name: str, hex: str, *, id: str | None = None) -> Color:
    """Create a color swatch.

    The hex value is not validated here; validation happens at the document
    boundary (see ``validate_project_document``).

    Args:
        name: Display name, e.g. ``"Matte Black"``.
        hex: Color value such as ``"#111111"``.
        id: Optional explicit id. A UUID4 string is generated when omitted.

    Returns:
        The new ``Color``. This function never fails for string arguments.
    """
    return Color(id=id if id is not None else _generate_id(), name=name, hex=hex)


def create_category(
    name: str,
    *,
    colors: Iterable[Color] = (),
    sub_categories: Iterable[Category] = (),
    id: str | None = None,
) -> Category:
    """Create a category.

    Args:
        name: Display name, e.g. ``"PLA"``.
        colors: Colors held directly by the category.
        sub_categories: Nested categories.
        id: Optional explicit id. A UUID4 string is generated when omitted.

    Returns:
        The new ``Category``. This function never fails for valid arguments.
    """
    return Category(
        id=id if id is not None else _generate_id(),
        name=name,
        colors=tuple(colors),
        sub_categories=tuple(sub_categories),
    )


def create_sub_category(
    name: str,
    *,
    colors: Iterable[Color] = (),
    sub_categories: Iterable[Category] = (),
    id: str | None = None,
) -> Category:
    """Create a category intended to be nested under another category.

    Sub-categories have the same shape as categories; this function exists for
    parity with the TypeScript API.

    Args:
        name: Display name.
        colors: Colors held directly by the sub-category.
        sub_categories: Further nested categories.
        id: Optional explicit id. A UUID4 string is generated when omitted.

    Returns:
        The new ``Category``. This function never fails for valid arguments.
    """
    return create_category(name, colors=colors, sub_categories=sub_categories, id=id)


def create_default_document() -> ProjectDocument:
    """Create an empty document with a sole ``"Default"`` category.

    Returns:
        A ``ProjectDocument`` with default style settings.
    """
    return ProjectDocument(categories=(create_category(DEFAULT_CATEGORY_NAME),))
