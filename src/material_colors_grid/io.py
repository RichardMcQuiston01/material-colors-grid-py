"""JSON import/export and file helpers for documents.

JSON document shape (keys are the Python field names, in snake_case)::

    {
      "categories": [
        {
          "id": "<uuid>",
          "name": "PLA",
          "colors": [{"id": "<uuid>", "name": "Matte Black", "hex": "#111111"}],
          "sub_categories": [ <category>, ... ]
        }
      ],
      "style": {
        "width": 1440,
        "height": 1280,
        "cards_per_row": 4,
        "background_color": "#ffffff",
        "card_background_color": "#ffffff",
        "card_border_color": "#cccccc",
        "card_border_thickness": 1,
        "card_corner_radius": 8,
        "card_font_color": "auto",
        "header": {"text": "", "background_color": "#ffffff",
                   "font_color": "#000000"},
        "footer": {"text": "", "background_color": "#ffffff",
                   "font_color": "#000000"},
        "watermark": {"image_path": null, "position": "bottom-right",
                      "scale": 0.15, "opacity": 0.5}
      }
    }

Only user-authored data is stored; the render model and layout are derived.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from material_colors_grid.atomic import write_bytes_atomically
from material_colors_grid.limits import MAX_JSON_INPUT_BYTES
from material_colors_grid.models import (
    BandStyle,
    Category,
    Color,
    ProjectDocument,
    Style,
    WatermarkPosition,
    WatermarkStyle,
)
from material_colors_grid.normalize import normalize_document
from material_colors_grid.result import Err, Ok, Result
from material_colors_grid.validate import (
    check_json_text,
    check_nesting_depth,
    describe_value,
    validate_project_document,
)


def document_to_json(document: ProjectDocument, *, indent: int | None = 2) -> str:
    """Serialize a document to a JSON string.

    Args:
        document: The document to serialize.
        indent: Indentation passed to ``json.dumps`` (``None`` for compact).

    Returns:
        JSON text in the shape described in this module's docstring. Any
        document the parsers accept is within the nesting limit, so this does
        not hit the recursion limit for them.
    """
    return json.dumps(asdict(document), indent=indent)


def _color_from_dict(raw: dict[str, Any]) -> Color:
    return Color(id=raw["id"], name=raw["name"], hex=raw["hex"])


def _category_from_dict(raw: dict[str, Any]) -> Category:
    return Category(
        id=raw["id"],
        name=raw["name"],
        colors=tuple(_color_from_dict(color) for color in raw["colors"]),
        sub_categories=tuple(
            _category_from_dict(child) for child in raw["sub_categories"]
        ),
    )


def _band_from_dict(raw: dict[str, Any]) -> BandStyle:
    return BandStyle(
        text=raw["text"],
        background_color=raw["background_color"],
        font_color=raw["font_color"],
    )


def _watermark_from_dict(raw: dict[str, Any]) -> WatermarkStyle:
    return WatermarkStyle(
        image_path=raw["image_path"],
        position=cast(WatermarkPosition, raw["position"]),
        scale=float(raw["scale"]),
        opacity=float(raw["opacity"]),
    )


def _style_from_dict(raw: dict[str, Any]) -> Style:
    return Style(
        width=raw["width"],
        height=raw["height"],
        cards_per_row=raw["cards_per_row"],
        background_color=raw["background_color"],
        card_background_color=raw["card_background_color"],
        card_border_color=raw["card_border_color"],
        card_border_thickness=raw["card_border_thickness"],
        card_corner_radius=raw["card_corner_radius"],
        card_font_color=raw["card_font_color"],
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
        fault (including limit violations, see ``limits``). Never raises for
        malformed data.
    """
    depth_error: str | None = check_nesting_depth(raw)
    if depth_error is not None:
        return Err(depth_error)
    try:
        validated = validate_project_document(normalize_document(raw))
        if isinstance(validated, Err):
            return validated
        data = validated.value
        return Ok(
            ProjectDocument(
                categories=tuple(
                    _category_from_dict(item) for item in data["categories"]
                ),
                style=_style_from_dict(data["style"]),
            )
        )
    except RecursionError:
        return Err("Document is nested too deeply to process")


def parse_imported_document(raw_json: str) -> Result[ProjectDocument]:
    """Parse JSON text into a document: decode, normalize, then validate.

    Args:
        raw_json: JSON text of a full or partial document.

    Returns:
        ``Ok`` with the document. ``Err`` when the text is too large or nested
        too deeply, is not valid JSON (with line/column), or the data fails
        validation (with JSON path and value). Never raises for bad input.
    """
    limit_error: str | None = check_json_text(raw_json)
    if limit_error is not None:
        return Err(limit_error)
    try:
        decoded: object = json.loads(raw_json)
    except json.JSONDecodeError as error:
        return Err(
            f"Invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"
        )
    except RecursionError:
        return Err("JSON is nested too deeply to parse")
    except ValueError as error:
        return Err(f"JSON contains a number that cannot be parsed: {error}")
    if not isinstance(decoded, dict):
        return Err(
            f"Document {describe_value(decoded)} is invalid (expected an object)"
        )
    return document_from_dict(decoded)


def load_document_file(path: str | Path) -> Result[ProjectDocument]:
    """Read and parse a document JSON file.

    Args:
        path: Location of the JSON file.

    Returns:
        ``Ok`` with the document. ``Err`` naming ``path`` when it cannot be
        read (missing, permission denied, not UTF-8) or its contents are
        invalid. A leading UTF-8 BOM is accepted.
    """
    file_path = Path(path)
    try:
        with file_path.open("rb") as handle:
            content: bytes = handle.read(MAX_JSON_INPUT_BYTES + 1)
        if len(content) > MAX_JSON_INPUT_BYTES:
            return Err(
                f'"{file_path}": file exceeds the maximum of '
                f"{MAX_JSON_INPUT_BYTES} bytes"
            )
        text = content.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        return Err(f'Cannot read "{file_path}": {error}')
    parsed = parse_imported_document(text)
    if isinstance(parsed, Err):
        return Err(f'"{file_path}": {parsed.error}')
    return parsed


def save_json_file(path: str | Path, text: str) -> Result[Path]:
    """Write JSON text to a file (UTF-8), safely and atomically.

    The destination must not be a symlink and, if it exists, must be a regular
    file. The text goes to a temporary file next to ``path`` and is moved into
    place, so a failure leaves no partial file.

    Args:
        path: Destination file. Parent directories must already exist.
        text: Text to write, usually from ``document_to_json``.

    Returns:
        ``Ok`` with the written ``Path``, or ``Err`` naming ``path`` when the
        write fails (symlink or non-regular destination, missing directory,
        permission denied, ...).
    """
    file_path = Path(path)
    try:
        encoded: bytes = text.encode("utf-8")
    except UnicodeEncodeError as error:
        return Err(f'Cannot write "{file_path}": text is not valid UTF-8: {error}')
    return write_bytes_atomically(file_path, encoded)
