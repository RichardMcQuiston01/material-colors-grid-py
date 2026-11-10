"""JSON import/export and file helpers for documents.

The JSON wire format is identical to the TypeScript package
``@richardmcquiston01/material-colors-grid`` (camelCase keys); the Python
dataclasses use snake_case and are converted here::

    {
      "categories": [
        {
          "id": "<uuid>",
          "name": "PLA",
          "colors": [{"id": "<uuid>", "name": "Matte Black", "hex": "#111111"}],
          "subCategories": [
            {"id": "<uuid>", "name": "Silk", "colors": [<color>, ...]}
          ]
        }
      ],
      "style": {
        "orientation": "landscape",     // "portrait" | "landscape"
        "aspectRatio": "4:3",
        "width": 1440,
        "height": 1280,
        "cardsPerRow": 5,
        "cardBackground": "#f7f7f7",
        "border": {"rounded": true, "thickness": "0.25rem", "color": "#dddddd"},
        "fonts": {
          "category": {"family": "Arial", "color": "#000000", "size": "1rem"},
          "subCategory": {"family": "Arial", "color": "#000000", "size": "0.85rem"},
          "card": {"family": "Arial", "color": "auto", "size": "0.75rem"}
        },
        "header": {
          "text": "",                   // empty text: band is not drawn
          "background": "#1b5e20",
          "font": {"family": "Arial", "color": "#ffffff", "size": "1.5rem"}
        },
        "footer": {
          "text": "",
          "background": "#1b5e20",
          "font": {"family": "Arial", "color": "#ffffff", "size": "0.85rem"}
        },
        "watermark": {
          "dataUrl": null,              // image data URL or null
          "position": "bottom-right",   // top-left|top-right|bottom-left|bottom-right
          "scale": 0.15,                // fraction of canvas width, 0..1
          "opacity": 1                  // 0..1
        }
      }
    }

Hex colors are 3 or 6 digits with a leading ``#``; the ``card`` font color may
also be ``"auto"``. Sizes are CSS sizes (``rem`` = 16px, ``px``, or a bare
number). Only user-authored data is stored; the render model and layout are
derived. Serialization is ``json.dumps(..., indent=2)`` with no wrapper keys,
like the TypeScript ``documentToJson``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from material_colors_grid.models import (
    BandStyle,
    BorderStyle,
    CardFontStyle,
    Category,
    Color,
    FontsStyle,
    FontStyle,
    Orientation,
    ProjectDocument,
    Style,
    SubCategory,
    WatermarkPosition,
    WatermarkStyle,
)
from material_colors_grid.normalize import normalize_document
from material_colors_grid.result import Err, Ok, Result
from material_colors_grid.validate import validate_project_document


def _color_to_dict(color: Color) -> dict[str, Any]:
    return {"id": color.id, "name": color.name, "hex": color.hex}


def _json_number(value: float) -> int | float:
    """Render whole floats as ints (``1`` not ``1.0``), as JavaScript does."""
    return int(value) if float(value).is_integer() else value


def _font_to_dict(font: FontStyle | CardFontStyle) -> dict[str, Any]:
    return {"family": font.family, "color": font.color, "size": font.size}


def _band_to_dict(band: BandStyle) -> dict[str, Any]:
    return {
        "text": band.text,
        "background": band.background,
        "font": _font_to_dict(band.font),
    }


def _sub_category_to_dict(sub_category: SubCategory) -> dict[str, Any]:
    return {
        "id": sub_category.id,
        "name": sub_category.name,
        "colors": [_color_to_dict(color) for color in sub_category.colors],
    }


def _category_to_dict(category: Category) -> dict[str, Any]:
    return {
        "id": category.id,
        "name": category.name,
        "colors": [_color_to_dict(color) for color in category.colors],
        "subCategories": [
            _sub_category_to_dict(child) for child in category.sub_categories
        ],
    }


def _style_to_dict(style: Style) -> dict[str, Any]:
    return {
        "orientation": style.orientation,
        "aspectRatio": style.aspect_ratio,
        "width": style.width,
        "height": style.height,
        "cardsPerRow": style.cards_per_row,
        "cardBackground": style.card_background,
        "border": {
            "rounded": style.border.rounded,
            "thickness": style.border.thickness,
            "color": style.border.color,
        },
        "fonts": {
            "category": _font_to_dict(style.fonts.category),
            "subCategory": _font_to_dict(style.fonts.sub_category),
            "card": _font_to_dict(style.fonts.card),
        },
        "header": _band_to_dict(style.header),
        "footer": _band_to_dict(style.footer),
        "watermark": {
            "dataUrl": style.watermark.data_url,
            "position": style.watermark.position,
            "scale": _json_number(style.watermark.scale),
            "opacity": _json_number(style.watermark.opacity),
        },
    }


def document_to_json(document: ProjectDocument, *, indent: int | None = 2) -> str:
    """Serialize a document to a JSON string.

    Args:
        document: The document to serialize.
        indent: Indentation passed to ``json.dumps`` (``None`` for compact).

    Returns:
        JSON text in the camelCase shape described in this module's docstring.
    """
    return json.dumps(
        {
            "categories": [_category_to_dict(item) for item in document.categories],
            "style": _style_to_dict(document.style),
        },
        indent=indent,
    )


def _color_from_dict(raw: dict[str, Any]) -> Color:
    return Color(id=raw["id"], name=raw["name"], hex=raw["hex"])


def _sub_category_from_dict(raw: dict[str, Any]) -> SubCategory:
    return SubCategory(
        id=raw["id"],
        name=raw["name"],
        colors=tuple(_color_from_dict(color) for color in raw["colors"]),
    )


def _category_from_dict(raw: dict[str, Any]) -> Category:
    return Category(
        id=raw["id"],
        name=raw["name"],
        colors=tuple(_color_from_dict(color) for color in raw["colors"]),
        sub_categories=tuple(
            _sub_category_from_dict(child) for child in raw["subCategories"]
        ),
    )


def _font_from_dict(raw: dict[str, Any]) -> FontStyle:
    return FontStyle(family=raw["family"], color=raw["color"], size=raw["size"])


def _card_font_from_dict(raw: dict[str, Any]) -> CardFontStyle:
    return CardFontStyle(family=raw["family"], color=raw["color"], size=raw["size"])


def _band_from_dict(raw: dict[str, Any]) -> BandStyle:
    return BandStyle(
        text=raw["text"],
        background=raw["background"],
        font=_font_from_dict(raw["font"]),
    )


def _watermark_from_dict(raw: dict[str, Any]) -> WatermarkStyle:
    return WatermarkStyle(
        data_url=raw["dataUrl"],
        position=cast(WatermarkPosition, raw["position"]),
        scale=float(raw["scale"]),
        opacity=float(raw["opacity"]),
    )


def _style_from_dict(raw: dict[str, Any]) -> Style:
    border: dict[str, Any] = raw["border"]
    fonts: dict[str, Any] = raw["fonts"]
    return Style(
        orientation=cast(Orientation, raw["orientation"]),
        aspect_ratio=raw["aspectRatio"],
        width=raw["width"],
        height=raw["height"],
        cards_per_row=raw["cardsPerRow"],
        card_background=raw["cardBackground"],
        border=BorderStyle(
            rounded=border["rounded"],
            thickness=border["thickness"],
            color=border["color"],
        ),
        fonts=FontsStyle(
            category=_font_from_dict(fonts["category"]),
            sub_category=_font_from_dict(fonts["subCategory"]),
            card=_card_font_from_dict(fonts["card"]),
        ),
        header=_band_from_dict(raw["header"]),
        footer=_band_from_dict(raw["footer"]),
        watermark=_watermark_from_dict(raw["watermark"]),
    )


def document_from_dict(raw: dict[str, Any]) -> Result[ProjectDocument]:
    """Build a ``ProjectDocument`` from a mapping, filling defaults.

    Args:
        raw: A (possibly partial) document mapping, e.g. from ``json.loads``.

    Returns:
        ``Ok`` with the document, or ``Err`` naming the JSON path and value at
        fault. Never raises for malformed data.
    """
    validated = validate_project_document(normalize_document(raw))
    if isinstance(validated, Err):
        return validated
    data = validated.value
    return Ok(
        ProjectDocument(
            categories=tuple(_category_from_dict(item) for item in data["categories"]),
            style=_style_from_dict(data["style"]),
        )
    )


def parse_imported_document(raw_json: str) -> Result[ProjectDocument]:
    """Parse JSON text into a document: decode, normalize, then validate.

    Args:
        raw_json: JSON text of a full or partial document.

    Returns:
        ``Ok`` with the document. ``Err`` when the text is not valid JSON
        (with line/column) or the data fails validation (with JSON path and
        value). Never raises for bad input.
    """
    try:
        decoded: object = json.loads(raw_json)
    except json.JSONDecodeError as error:
        return Err(
            f"Invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"
        )
    if not isinstance(decoded, dict):
        return Err(
            f"Document {json.dumps(decoded)[:60]} is invalid (expected an object)"
        )
    return document_from_dict(decoded)


def load_document_file(path: str | Path) -> Result[ProjectDocument]:
    """Read and parse a document JSON file.

    Args:
        path: Location of the JSON file.

    Returns:
        ``Ok`` with the document. ``Err`` naming ``path`` when it cannot be
        read (missing, permission denied, not UTF-8) or its contents are
        invalid.
    """
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return Err(f'Cannot read "{file_path}": {error}')
    parsed = parse_imported_document(text)
    if isinstance(parsed, Err):
        return Err(f'"{file_path}": {parsed.error}')
    return parsed


def save_json_file(path: str | Path, text: str) -> Result[Path]:
    """Write JSON text to a file (UTF-8).

    Args:
        path: Destination file. Parent directories must already exist.
        text: Text to write, usually from ``document_to_json``.

    Returns:
        ``Ok`` with the written ``Path``, or ``Err`` naming ``path`` when the
        write fails (missing directory, permission denied, ...).
    """
    file_path = Path(path)
    try:
        file_path.write_text(text, encoding="utf-8")
    except OSError as error:
        return Err(f'Cannot write "{file_path}": {error}')
    return Ok(file_path)
