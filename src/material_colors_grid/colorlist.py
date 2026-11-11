"""Convert the simple color-list form into a ``ProjectDocument``.

The simple form is a JSON array of objects, handy for scripts and plugins::

    [{"name": "Matte Black", "hex": "#111111", "category": "PLA"}]

``name`` and ``hex`` are required. ``category`` and ``sub_category`` are
optional strings. Colors without a ``category`` go in the ``"Default"``
category. A ``sub_category`` without a ``category`` is nested under
``"Default"``.

Category and sub-category names group case-insensitively and ignoring
surrounding whitespace (``"PLA"``, ``"pla"`` and ``" PLA "`` are one
category); the first spelling seen, trimmed, is kept.
"""

from __future__ import annotations

import json

from material_colors_grid.defaults import (
    DEFAULT_CATEGORY_NAME,
    create_category,
    create_color,
    create_sub_category,
)
from material_colors_grid.limits import MAX_CATEGORIES, MAX_COLORS, MAX_NAME_LENGTH
from material_colors_grid.models import Category, Color, ProjectDocument
from material_colors_grid.result import Err, Ok, Result
from material_colors_grid.validate import (
    check_json_text,
    check_nesting_depth,
    check_text_length,
    describe_value,
    is_hex_color,
)

_KNOWN_KEYS: frozenset[str] = frozenset({"name", "hex", "category", "sub_category"})


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
            f"{path} {describe_value(value)} is invalid (expected a non-empty string)"
        )
    length_error: str | None = (
        check_text_length(path, value, MAX_NAME_LENGTH) if key != "hex" else None
    )
    if length_error is not None:
        return Err(length_error)
    return Ok(value)


def _group_key(name: str) -> str:
    """Grouping key for a category name: trimmed and case-folded."""
    return name.strip().casefold()


def _parse_entry(entry: object, index: int) -> Result[tuple[Color, str, str | None]]:
    """Validate one list item into ``(color, category_name, sub_category_name)``."""
    if not isinstance(entry, dict):
        return Err(
            f"colors[{index}] {describe_value(entry)} is invalid (expected an object)"
        )
    unknown: list[str] = sorted(str(key) for key in entry if key not in _KNOWN_KEYS)
    if unknown:
        return Err(
            f"colors[{index}].{unknown[0][:40]} "
            f"{describe_value(entry[unknown[0]])} is "
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
            f"colors[{index}].hex {describe_value(hex_value)} is invalid "
            f'for color "{name}" (expected 3 or 6 hex digits with a leading #)'
        )
    category_name: str = (fields["category"] or DEFAULT_CATEGORY_NAME).strip()
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
        return Err(
            f"Color list {describe_value(raw)[:60]} is invalid (expected an array)"
        )
    depth_error: str | None = check_nesting_depth(raw)
    if depth_error is not None:
        return Err(depth_error)
    if len(raw) > MAX_COLORS:
        return Err(
            f"Color list has {len(raw)} entries, which exceeds the maximum of "
            f"{MAX_COLORS}"
        )
    # Grouping key -> first-seen spelling, so "PLA" and "pla" share a category.
    spellings: dict[str, str] = {}
    sub_spellings: dict[str, dict[str, str]] = {}
    direct: dict[str, list[Color]] = {}
    nested: dict[str, dict[str, list[Color]]] = {}
    for index, entry in enumerate(raw):
        parsed: Result[tuple[Color, str, str | None]] = _parse_entry(entry, index)
        if isinstance(parsed, Err):
            return parsed
        color, category_name, sub_category_name = parsed.value
        category_key: str = _group_key(category_name)
        spellings.setdefault(category_key, category_name)
        direct.setdefault(category_key, [])
        if sub_category_name is None:
            direct[category_key].append(color)
        else:
            sub_key: str = _group_key(sub_category_name)
            sub_spellings.setdefault(category_key, {}).setdefault(
                sub_key, sub_category_name.strip()
            )
            groups: dict[str, list[Color]] = nested.setdefault(category_key, {})
            groups.setdefault(sub_key, []).append(color)
    category_total: int = len(direct) + sum(len(groups) for groups in nested.values())
    if category_total > MAX_CATEGORIES:
        return Err(
            f"Color list forms {category_total} categories and sub-categories, "
            f"which exceeds the maximum of {MAX_CATEGORIES}"
        )
    categories: list[Category] = [
        create_category(
            spellings[key],
            colors=colors,
            sub_categories=[
                create_sub_category(sub_spellings[key][sub_key], colors=sub_colors)
                for sub_key, sub_colors in nested.get(key, {}).items()
            ],
        )
        for key, colors in direct.items()
    ]
    if not categories:
        categories = [create_category(DEFAULT_CATEGORY_NAME)]
    return Ok(ProjectDocument(categories=tuple(categories)))


def parse_color_list(raw_json: str) -> Result[ProjectDocument]:
    """Parse JSON text of a simple color list into a document.

    Args:
        raw_json: JSON text of the list.

    Returns:
        ``Ok`` with the document, or ``Err`` for text that is too large or
        nested too deeply, invalid JSON (with line and column) or an invalid
        entry (see ``color_list_to_document``).
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
    return color_list_to_document(decoded)
