"""Domain models for a color grid document.

Mirrors the document structure of the TypeScript package
``@richardmcquiston01/material-colors-grid`` with snake_case field names.
``io.py`` converts between these dataclasses and the camelCase JSON wire
format, so documents are portable between both libraries. Defaults here are
the TypeScript package's defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

Orientation = Literal["portrait", "landscape"]
WatermarkPosition = Literal["top-left", "top-right", "bottom-left", "bottom-right"]

ORIENTATIONS: Final[tuple[Orientation, ...]] = ("portrait", "landscape")
WATERMARK_POSITIONS: Final[tuple[WatermarkPosition, ...]] = (
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
)


@dataclass(frozen=True, slots=True)
class Color:
    """A single color swatch."""

    id: str
    name: str
    hex: str


@dataclass(frozen=True, slots=True)
class SubCategory:
    """A named group of colors inside a category (one level deep only)."""

    id: str
    name: str
    colors: tuple[Color, ...] = ()


@dataclass(frozen=True, slots=True)
class Category:
    """A named group of colors and/or sub-categories."""

    id: str
    name: str
    colors: tuple[Color, ...] = ()
    sub_categories: tuple[SubCategory, ...] = ()


@dataclass(frozen=True, slots=True)
class FontStyle:
    """Font for headings and bands. ``size`` is a CSS size such as ``1rem``."""

    family: str = "Arial"
    color: str = "#000000"
    size: str = "1rem"


@dataclass(frozen=True, slots=True)
class CardFontStyle:
    """Font for color cards. ``color`` is ``"auto"`` or a hex color."""

    family: str = "Arial"
    color: str = "auto"
    size: str = "0.75rem"


@dataclass(frozen=True, slots=True)
class FontsStyle:
    """Fonts for category headings, sub-category headings, and cards."""

    category: FontStyle = field(default_factory=FontStyle)
    sub_category: FontStyle = field(default_factory=lambda: FontStyle(size="0.85rem"))
    card: CardFontStyle = field(default_factory=CardFontStyle)


@dataclass(frozen=True, slots=True)
class BorderStyle:
    """Card border. ``thickness`` is a CSS size such as ``0.25rem``."""

    rounded: bool = True
    thickness: str = "0.25rem"
    color: str = "#dddddd"


@dataclass(frozen=True, slots=True)
class BandStyle:
    """Header or footer band. Rendered only when ``text`` is non-empty."""

    text: str = ""
    background: str = "#1b5e20"
    font: FontStyle = field(
        default_factory=lambda: FontStyle(color="#ffffff", size="1.5rem")
    )


@dataclass(frozen=True, slots=True)
class WatermarkStyle:
    """Corner watermark. ``scale`` is a fraction (0..1) of the canvas width."""

    data_url: str | None = None
    position: WatermarkPosition = "bottom-right"
    scale: float = 0.15
    opacity: float = 1.0


@dataclass(frozen=True, slots=True)
class Style:
    """Visual settings for the rendered grid."""

    orientation: Orientation = "landscape"
    aspect_ratio: str = "4:3"
    width: int = 1440
    height: int = 1280
    cards_per_row: int = 5
    card_background: str = "#f7f7f7"
    border: BorderStyle = field(default_factory=BorderStyle)
    fonts: FontsStyle = field(default_factory=FontsStyle)
    header: BandStyle = field(default_factory=BandStyle)
    footer: BandStyle = field(
        default_factory=lambda: BandStyle(
            font=FontStyle(color="#ffffff", size="0.85rem")
        )
    )
    watermark: WatermarkStyle = field(default_factory=WatermarkStyle)


@dataclass(frozen=True, slots=True)
class ProjectDocument:
    """A complete, JSON-serializable color grid document."""

    categories: tuple[Category, ...] = ()
    style: Style = field(default_factory=Style)
