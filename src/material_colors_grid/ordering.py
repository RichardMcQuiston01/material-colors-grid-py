"""Sorting and the derived render model (pure, no Pillow, never persisted).

Ordering rules: categories alphabetical (case-insensitive), sub-categories
alphabetical, colors dark to light by WCAG luminance. Ties break on name
then id so output is deterministic. Colors with an invalid hex have unknown
luminance and sort after all valid colors (by name, then id) instead of
raising; validation reports them elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass

from material_colors_grid.color import parse_hex, relative_luminance
from material_colors_grid.models import (
    Category,
    Color,
    ProjectDocument,
    SubCategory,
)
from material_colors_grid.result import Err, Result

DEFAULT_CATEGORY_NAME: str = "Default"


@dataclass(frozen=True, slots=True)
class RenderColor:
    """A color ready to draw. ``luminance`` is ``None`` for an invalid hex."""

    id: str
    name: str
    hex: str
    luminance: float | None


@dataclass(frozen=True, slots=True)
class RenderCategory:
    """A sorted category. ``depth`` is 0 for top-level categories."""

    id: str
    name: str
    depth: int
    show_header: bool
    colors: tuple[RenderColor, ...]
    sub_categories: tuple[RenderCategory, ...]


@dataclass(frozen=True, slots=True)
class RenderModel:
    """Sorted, display-ready view of a document's categories."""

    categories: tuple[RenderCategory, ...]


def _to_render_color(color: Color) -> RenderColor:
    """Attach luminance (or ``None`` when the hex is invalid) to a color."""
    parsed: Result[tuple[int, int, int]] = parse_hex(color.hex)
    luminance: float | None = None
    if not isinstance(parsed, Err):
        luminance = relative_luminance(*parsed.value)
    return RenderColor(id=color.id, name=color.name, hex=color.hex, luminance=luminance)


def _color_sort_key(color: RenderColor) -> tuple[int, float, str, str, str]:
    """Dark to light; unknown luminance last; ties by name then id."""
    unknown: int = 1 if color.luminance is None else 0
    luminance: float = 0.0 if color.luminance is None else color.luminance
    return (unknown, luminance, color.name.casefold(), color.name, color.id)


def _category_sort_key(category: Category | SubCategory) -> tuple[str, str, str]:
    """Alphabetical, case-insensitive; ties by exact name then id."""
    return (category.name.casefold(), category.name, category.id)


def _is_default_name(name: str) -> bool:
    """Return True when ``name`` is "Default" (case-insensitive, trimmed)."""
    return name.strip().casefold() == DEFAULT_CATEGORY_NAME.casefold()


def _build_category(
    category: Category | SubCategory, depth: int, show_header: bool
) -> RenderCategory:
    """Sort one category's colors and its (one level deep) sub-categories."""
    colors: tuple[RenderColor, ...] = tuple(
        sorted(
            (_to_render_color(color) for color in category.colors),
            key=_color_sort_key,
        )
    )
    children: list[SubCategory] = (
        sorted(category.sub_categories, key=_category_sort_key)
        if isinstance(category, Category)
        else []
    )
    return RenderCategory(
        id=category.id,
        name=category.name,
        depth=depth,
        show_header=show_header,
        colors=colors,
        sub_categories=tuple(
            _build_category(child, depth + 1, True) for child in children
        ),
    )


def build_render_model(document: ProjectDocument) -> RenderModel:
    """Build the sorted render model for a document.

    Args:
        document: The document to order.

    Returns:
        A frozen ``RenderModel``. A sole top-level category named "Default"
        has ``show_header=False``; every other category shows its header.
        Colors with invalid hex sort last. Never raises for bad data.
    """
    ordered: list[Category] = sorted(document.categories, key=_category_sort_key)
    is_sole_default: bool = len(ordered) == 1 and _is_default_name(ordered[0].name)
    return RenderModel(
        categories=tuple(
            _build_category(category, 0, not is_sole_default) for category in ordered
        )
    )
