"""Pure layout engine: absolute pixel rectangles, no drawing, no Pillow.

Geometry (all values in pixels, origin at top-left):

* ``MARGIN`` surrounds the content area on the left, right, and between the
  header band / content / footer band.
* The header band (when ``style.header.text`` is non-empty) spans the full
  canvas width at y=0 with height ``BAND_HEIGHT``; the footer band likewise,
  pinned to the bottom edge of the canvas.
* Content starts ``MARGIN`` below the header (or at ``MARGIN`` with no header).
* Each category with ``show_header`` gets a heading rectangle of height
  ``HEADING_HEIGHT`` followed by ``HEADING_GAP``. Sub-categories follow their
  parent's own colors and are indented by ``INDENT`` per depth level.
  Sections are separated by ``SECTION_GAP``.
* Cards are ``CARD_HEIGHT`` tall and ``CARD_GAP`` apart, wrapping at
  ``style.cards_per_row`` (values below 1 act as 1). Card width is derived so
  a row fills the content width, but never drops below ``MIN_CARD_WIDTH``;
  if it would, the canvas widens instead.
* Canvas width is ``max(style.width, required width)`` and canvas height is
  ``max(style.height, content bottom + MARGIN + footer height)``, so content
  is never clipped.
"""

from __future__ import annotations

from dataclasses import dataclass

from material_colors_grid.models import Style
from material_colors_grid.ordering import RenderCategory, RenderColor, RenderModel

MARGIN: int = 40
BAND_HEIGHT: int = 100
HEADING_HEIGHT: int = 48
HEADING_GAP: int = 16
CARD_HEIGHT: int = 200
CARD_GAP: int = 24
SECTION_GAP: int = 32
INDENT: int = 24
MIN_CARD_WIDTH: int = 120


@dataclass(frozen=True, slots=True)
class Rect:
    """An absolute rectangle in canvas pixels."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class HeadingLayout:
    """A category heading and where to draw it."""

    category_id: str
    text: str
    depth: int
    rect: Rect


@dataclass(frozen=True, slots=True)
class CardLayout:
    """A color card and where to draw it."""

    category_id: str
    color: RenderColor
    rect: Rect


@dataclass(frozen=True, slots=True)
class BandLayout:
    """A header or footer band."""

    text: str
    rect: Rect


@dataclass(frozen=True, slots=True)
class Layout:
    """Complete derived layout. Never persisted."""

    width: int
    height: int
    header: BandLayout | None
    footer: BandLayout | None
    headings: tuple[HeadingLayout, ...]
    cards: tuple[CardLayout, ...]


def _flatten(categories: tuple[RenderCategory, ...]) -> list[RenderCategory]:
    """Flatten depth-first, parent before children, keeping sorted order."""
    flattened: list[RenderCategory] = []
    for category in categories:
        flattened.append(category)
        flattened.extend(_flatten(category.sub_categories))
    return flattened


def compute_layout(render_model: RenderModel, style: Style) -> Layout:
    """Compute pixel rectangles for every element of the grid.

    Args:
        render_model: Output of ``build_render_model``.
        style: Style settings (canvas size, cards per row, header/footer).

    Returns:
        A frozen ``Layout``. Bands are ``None`` when their text is empty.
        The canvas grows past ``style.width``/``style.height`` if needed.
    """
    columns: int = max(1, style.cards_per_row)
    flattened: list[RenderCategory] = _flatten(render_model.categories)
    has_header: bool = style.header.text != ""
    has_footer: bool = style.footer.text != ""

    deepest_indent: int = max((item.depth for item in flattened), default=0) * INDENT
    minimum_width: int = (
        2 * MARGIN
        + columns * MIN_CARD_WIDTH
        + (columns - 1) * CARD_GAP
        + deepest_indent
    )
    canvas_width: int = max(style.width, minimum_width)
    content_width: int = canvas_width - 2 * MARGIN

    headings: list[HeadingLayout] = []
    cards: list[CardLayout] = []
    cursor_y: int = (BAND_HEIGHT if has_header else 0) + MARGIN
    is_first_section: bool = True

    for category in flattened:
        if not category.show_header and not category.colors:
            continue
        if not is_first_section:
            cursor_y += SECTION_GAP
        is_first_section = False
        left: int = MARGIN + category.depth * INDENT
        available: int = content_width - category.depth * INDENT
        if category.show_header:
            headings.append(
                HeadingLayout(
                    category_id=category.id,
                    text=category.name,
                    depth=category.depth,
                    rect=Rect(left, cursor_y, available, HEADING_HEIGHT),
                )
            )
            cursor_y += HEADING_HEIGHT + HEADING_GAP
        card_width: int = (available - (columns - 1) * CARD_GAP) // columns
        for index, color in enumerate(category.colors):
            row, column = divmod(index, columns)
            cards.append(
                CardLayout(
                    category_id=category.id,
                    color=color,
                    rect=Rect(
                        left + column * (card_width + CARD_GAP),
                        cursor_y + row * (CARD_HEIGHT + CARD_GAP),
                        card_width,
                        CARD_HEIGHT,
                    ),
                )
            )
        if category.colors:
            rows: int = -(-len(category.colors) // columns)
            cursor_y += rows * CARD_HEIGHT + (rows - 1) * CARD_GAP

    footer_height: int = BAND_HEIGHT if has_footer else 0
    canvas_height: int = max(style.height, cursor_y + MARGIN + footer_height)

    header: BandLayout | None = None
    if has_header:
        header = BandLayout(style.header.text, Rect(0, 0, canvas_width, BAND_HEIGHT))
    footer: BandLayout | None = None
    if has_footer:
        footer = BandLayout(
            style.footer.text,
            Rect(0, canvas_height - BAND_HEIGHT, canvas_width, BAND_HEIGHT),
        )
    return Layout(
        width=canvas_width,
        height=canvas_height,
        header=header,
        footer=footer,
        headings=tuple(headings),
        cards=tuple(cards),
    )
