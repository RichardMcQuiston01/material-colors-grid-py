"""Fill missing fields in partial documents with defaults."""

from __future__ import annotations

import math
import uuid
from dataclasses import asdict
from typing import Any, Final

from material_colors_grid.models import Style

_INTEGER_STYLE_KEYS: Final = (
    "width",
    "height",
    "cards_per_row",
    "card_border_thickness",
    "card_corner_radius",
)


def _default_style() -> dict[str, Any]:
    return asdict(Style())


def _merge_mapping(defaults: dict[str, Any], provided: object) -> object:
    """Overlay ``provided`` on ``defaults``, recursing into nested mappings.

    A non-mapping ``provided`` is returned unchanged so validation can report
    it. ``None`` values fall back to the default, except where the default
    itself is ``None`` (e.g. ``watermark.image_path``).
    """
    if not isinstance(provided, dict):
        return provided
    merged: dict[str, Any] = dict(provided)
    for key, default_value in defaults.items():
        if key not in merged or (merged[key] is None and default_value is not None):
            merged[key] = default_value
        elif isinstance(default_value, dict):
            merged[key] = _merge_mapping(default_value, merged[key])
    return merged


def _whole_float_to_int(value: object) -> object:
    """Turn a finite whole float (``1440.0``, ``1e3``) into an ``int``.

    Everything else (ints, bools, fractions, NaN, infinity, other types) is
    returned unchanged so validation can report it.
    """
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return value


def _normalize_color(color: object) -> object:
    if not isinstance(color, dict):
        return color
    normalized: dict[str, Any] = dict(color)
    if normalized.get("id") is None:
        normalized["id"] = str(uuid.uuid4())
    return normalized


def _normalize_category(category: object) -> object:
    if not isinstance(category, dict):
        return category
    normalized: dict[str, Any] = dict(category)
    if normalized.get("id") is None:
        normalized["id"] = str(uuid.uuid4())
    for key, normalize_item in (
        ("colors", _normalize_color),
        ("sub_categories", _normalize_category),
    ):
        items = normalized.get(key)
        if items is None:
            normalized[key] = []
        elif isinstance(items, list):
            normalized[key] = [normalize_item(item) for item in items]
    return normalized


def normalize_document(raw: object) -> object:
    """Fill missing fields of a partial document mapping with defaults.

    Missing ``style`` values come from ``Style``; missing ids are generated.
    Required user data (``name``, ``hex``) is never invented, so validation
    still reports it. Whole-number floats in integer style fields (``1440.0``,
    ``1e3``) become ints; fractions, NaN and infinity are left for validation
    to reject. The input is not modified and this function never
    raises: anything that is not a mapping is returned unchanged.

    Args:
        raw: Untrusted data, typically from ``json.loads``.

    Returns:
        A new mapping with defaults applied, or ``raw`` unchanged when it is
        not a mapping.
    """
    if not isinstance(raw, dict):
        return raw
    normalized: dict[str, Any] = dict(raw)
    categories = normalized.get("categories")
    if categories is None:
        normalized["categories"] = []
    elif isinstance(categories, list):
        normalized["categories"] = [_normalize_category(item) for item in categories]
    style = normalized.get("style")
    merged_style: object = _merge_mapping(
        _default_style(), {} if style is None else style
    )
    if isinstance(merged_style, dict):
        for key in _INTEGER_STYLE_KEYS:
            merged_style[key] = _whole_float_to_int(merged_style[key])
    normalized["style"] = merged_style
    return normalized
