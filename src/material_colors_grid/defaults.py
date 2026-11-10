"""Factories for documents, categories, and colors with generated ids."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from material_colors_grid.models import (
    Category,
    Color,
    ProjectDocument,
    Style,
    SubCategory,
)

DEFAULT_CATEGORY_ID = "default"
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
    sub_categories: Iterable[SubCategory] = (),
    id: str | None = None,
) -> Category:
    """Create a category.

    Args:
        name: Display name, e.g. ``"PLA"``.
        colors: Colors held directly by the category.
        sub_categories: Sub-categories (one level deep).
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
    id: str | None = None,
) -> SubCategory:
    """Create a sub-category to place inside a category.

    Args:
        name: Display name.
        colors: Colors held by the sub-category.
        id: Optional explicit id. A UUID4 string is generated when omitted.

    Returns:
        The new ``SubCategory``. This function never fails for valid arguments.
    """
    return SubCategory(
        id=id if id is not None else _generate_id(),
        name=name,
        colors=tuple(colors),
    )


def create_default_style() -> Style:
    """Create the default style settings (identical to the TypeScript package).

    Returns:
        A ``Style`` with 1440x1280 landscape canvas, 5 cards per row, empty
        header/footer text and no watermark.
    """
    return Style()


def create_default_document() -> ProjectDocument:
    """Create an empty document with a sole ``"Default"`` category.

    Returns:
        A ``ProjectDocument`` whose category has id ``"default"``, plus the
        default style.
    """
    return ProjectDocument(
        categories=(create_category(DEFAULT_CATEGORY_NAME, id=DEFAULT_CATEGORY_ID),),
        style=create_default_style(),
    )
