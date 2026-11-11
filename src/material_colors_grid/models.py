"""Domain models for a color grid document.

Mirrors the document shape of the TypeScript package
``@richardmcquiston01/material-colors-grid`` so documents are portable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

WatermarkPosition = Literal[
    "top-left", "top-right", "bottom-left", "bottom-right", "center"
]


@dataclass(frozen=True, slots=True)
class Color:
    """A single color swatch."""

    id: str
    name: str
    hex: str


@dataclass(frozen=True, slots=True)
class Category:
    """A named group of colors and/or sub-categories."""

    id: str
    name: str
    colors: tuple[Color, ...] = ()
    sub_categories: tuple[Category, ...] = ()


@dataclass(frozen=True, slots=True)
class BandStyle:
    """Header or footer band. Rendered only when ``text`` is non-empty."""

    text: str = ""
    background_color: str = "#ffffff"
    font_color: str = "#000000"


@dataclass(frozen=True, slots=True)
class WatermarkStyle:
    """Corner watermark settings.

    ``image_path`` is stored for round-tripping only. It is ignored by the CLI
    and by ``render_to_image`` (documents are untrusted, so no file named in a
    document is ever opened). Pass the image explicitly instead, via the
    ``watermark_image`` argument or the CLI ``--watermark`` flag.
    """

    image_path: str | None = None
    position: WatermarkPosition = "bottom-right"
    scale: float = 0.15
    opacity: float = 0.5


@dataclass(frozen=True, slots=True)
class Style:
    """Visual settings for the rendered grid."""

    width: int = 1440
    height: int = 1280
    cards_per_row: int = 4
    background_color: str = "#ffffff"
    card_background_color: str = "#ffffff"
    card_border_color: str = "#cccccc"
    card_border_thickness: int = 1
    card_corner_radius: int = 8
    card_font_color: str = "auto"
    header: BandStyle = field(default_factory=BandStyle)
    footer: BandStyle = field(default_factory=BandStyle)
    watermark: WatermarkStyle = field(default_factory=WatermarkStyle)


@dataclass(frozen=True, slots=True)
class ProjectDocument:
    """A complete, JSON-serializable color grid document."""

    categories: tuple[Category, ...] = ()
    style: Style = field(default_factory=Style)
