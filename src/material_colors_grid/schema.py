"""Hand-written JSON Schema (draft 2020-12) for the document format.

Kept in sync with ``models.py`` and ``validate.py`` by tests. It describes
what the CLI and ``parse_imported_document`` accept: partial documents are
fine because ``normalize_document`` fills defaults, so only user data
(``name``, ``hex``) is required.
"""

from __future__ import annotations

import copy
from typing import Any, Final

_HEX: Final[dict[str, Any]] = {
    "type": "string",
    "pattern": "^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
}

DOCUMENT_JSON_SCHEMA: Final[dict[str, Any]] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ProjectDocument",
    "description": "A material-colors-grid document: categories plus style.",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "categories": {"type": "array", "items": {"$ref": "#/$defs/category"}},
        "style": {"$ref": "#/$defs/style"},
    },
    "$defs": {
        "color": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "hex"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "hex": {**_HEX, "description": "3 or 6 hex digits, leading #."},
            },
        },
        "category": {
            "type": "object",
            "description": "Holds colors and/or nested sub-categories.",
            "additionalProperties": False,
            "required": ["name"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "colors": {"type": "array", "items": {"$ref": "#/$defs/color"}},
                "sub_categories": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/category"},
                },
            },
        },
        "band": {
            "type": "object",
            "description": "Header/footer band; drawn only when text is non-empty.",
            "additionalProperties": False,
            "properties": {
                "text": {"type": "string", "default": ""},
                "background_color": {**_HEX, "default": "#ffffff"},
                "font_color": {**_HEX, "default": "#000000"},
            },
        },
        "watermark": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "image_path": {"type": ["string", "null"], "default": None},
                "position": {
                    "enum": [
                        "top-left",
                        "top-right",
                        "bottom-left",
                        "bottom-right",
                        "center",
                    ],
                    "default": "bottom-right",
                },
                "scale": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "maximum": 1,
                    "default": 0.15,
                },
                "opacity": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 0.5,
                },
            },
        },
        "style": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "width": {"type": "integer", "minimum": 1, "default": 1440},
                "height": {"type": "integer", "minimum": 1, "default": 1280},
                "cards_per_row": {"type": "integer", "minimum": 1, "default": 4},
                "background_color": {**_HEX, "default": "#ffffff"},
                "card_background_color": {**_HEX, "default": "#ffffff"},
                "card_border_color": {**_HEX, "default": "#cccccc"},
                "card_border_thickness": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 1,
                },
                "card_corner_radius": {"type": "integer", "minimum": 0, "default": 8},
                "card_font_color": {
                    "anyOf": [{"const": "auto"}, _HEX],
                    "default": "auto",
                },
                "header": {"$ref": "#/$defs/band"},
                "footer": {"$ref": "#/$defs/band"},
                "watermark": {"$ref": "#/$defs/watermark"},
            },
        },
    },
}


def document_json_schema() -> dict[str, Any]:
    """Return a copy of the document JSON Schema (draft 2020-12).

    Returns:
        A new dict that callers may modify without affecting the original.
    """
    return copy.deepcopy(DOCUMENT_JSON_SCHEMA)
