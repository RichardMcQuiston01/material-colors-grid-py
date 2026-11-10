"""Convert the simple color-list form into a ``ProjectDocument``.

The simple form is a JSON array of objects, handy for scripts and plugins::

    [{"name": "Matte Black", "hex": "#111111", "category": "PLA"}]

``name`` and ``hex`` are required. ``category`` and ``sub_category`` are
optional strings. Colors without a ``category`` go in the ``"Default"``
category. A ``sub_category`` without a ``category`` is nested under
``"Default"``.
"""

from __future__ import annotations

import json

from material_colors_grid.defaults import (
    DEFAULT_CATEGORY_NAME,
    create_category,
    create_color,
    create_sub_category,
)
from material_colors_grid.models import Category, Color, ProjectDocument
from material_colors_grid.result import Err, Ok, Result
from material_colors_grid.validate import is_hex_color

_KNOWN_KEYS: frozenset[str] = frozenset({"name", "hex", "category", "sub_category"})


def _describe(value: object) -> str:
    """Render a value for an error message, JSON style."""
    return json.dumps(value, ensure_ascii=False, default=repr)


def _text_field(
    entry: dict[str, object], index: int, key: str, *, required: bool
) -> Result[str | None]:
    """Read a string field, returning ``Ok(None)`` for an optional absent one."""
    path: str = f"colors[{index}].{key}"
    value: object = entry.get(key)
    if value is None:
        return Err(f"{path} is missing") if required else Ok(None)
    if not isinstance(value, str) or not value.strip():
        return Err(
            f"{path} {_describe(value)} is invalid (expected a non-empty string)"
        )
    return Ok(value)


def _parse_entry(entry: object, index: int) -> Result[tuple[Color, str, str | None]]:
    """Validate one list item into ``(color, category_name, sub_category_name)``."""
    if not isinstance(entry, dict):
        return Err(
            f"colors[{index}] {_describe(entry)} is invalid (expected an object)"
        )
    unknown: list[str] = sorted(str(key) for key in entry if key not in _KNOWN_KEYS)
    if unknown:
        return Err(
            f"colors[{index}].{unknown[0]} {_describe(entry[unknown[0]])} is "
            "invalid (expected one of name, hex, category, sub_category)"
        )
    fields: dict[str, str | None] = {}
    for key, required in (
        ("name", True),
        ("hex", True),
        ("category", False),
        ("sub_category", False),
    ):
        field: Result[str | None] = _text_field(entry, index, key, required=required)
        if isinstance(field, Err):
            return field
        fields[key] = field.value
    hex_value: str | None = fields["hex"]
    name: str | None = fields["name"]
    if name is None or hex_value is None or not is_hex_color(hex_value):
        return Err(
            f"colors[{index}].hex {_describe(hex_value)} is invalid "
            f'for color "{name}" (expected 3 or 6 hex digits with a leading #)'
        )
    category_name: str = fields["category"] or DEFAULT_CATEGORY_NAME
    return Ok((create_color(name, hex_value), category_name, fields["sub_category"]))


def color_list_to_document(raw: object) -> Result[ProjectDocument]:
    """Build a document from a decoded simple color list.

    Categories and sub-categories keep first-seen order (rendering sorts them).

    Args:
        raw: Decoded JSON, expected to be a list of objects with ``name``,
            ``hex`` and optional ``category`` / ``sub_category`` strings.

    Returns:
        ``Ok`` with a document using default style, or ``Err`` naming the list
        index, field and value at fault (for example
        ``colors[2].hex "#12" is invalid for color "Matte Black" ...``).
        Never raises for bad data.
    """
    if not isinstance(raw, list):
        return Err(f"Color list {_describe(raw)[:60]} is invalid (expected an array)")
    direct: dict[str, list[Color]] = {}
    nested: dict[str, dict[str, list[Color]]] = {}
    for index, entry in enumerate(raw):
        parsed: Result[tuple[Color, str, str | None]] = _parse_entry(entry, index)
        if isinstance(parsed, Err):
            return parsed
        color, category_name, sub_category_name = parsed.value
        direct.setdefault(category_name, [])
        if sub_category_name is None:
            direct[category_name].append(color)
        else:
            groups: dict[str, list[Color]] = nested.setdefault(category_name, {})
            groups.setdefault(sub_category_name, []).append(color)
    categories: list[Category] = [
        create_category(
            name,
            colors=colors,
            sub_categories=[
                create_sub_category(sub_name, colors=sub_colors)
                for sub_name, sub_colors in nested.get(name, {}).items()
            ],
        )
        for name, colors in direct.items()
    ]
    if not categories:
        categories = [create_category(DEFAULT_CATEGORY_NAME)]
    return Ok(ProjectDocument(categories=tuple(categories)))


def parse_color_list(raw_json: str) -> Result[ProjectDocument]:
    """Parse JSON text of a simple color list into a document.

    Args:
        raw_json: JSON text of the list.

    Returns:
        ``Ok`` with the document, or ``Err`` for invalid JSON (with line and
        column) or an invalid entry (see ``color_list_to_document``).
    """
    try:
        decoded: object = json.loads(raw_json)
    except json.JSONDecodeError as error:
        return Err(
            f"Invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"
        )
    return color_list_to_document(decoded)
