"""Fill missing fields in partial documents with defaults."""

from __future__ import annotations

import copy
import uuid
from typing import Any, Final

_DEFAULT_STYLE: Final[dict[str, Any]] = {
    "orientation": "landscape",
    "aspectRatio": "4:3",
    "width": 1440,
    "height": 1280,
    "cardsPerRow": 5,
    "cardBackground": "#f7f7f7",
    "border": {"rounded": True, "thickness": "0.25rem", "color": "#dddddd"},
    "fonts": {
        "category": {"family": "Arial", "color": "#000000", "size": "1rem"},
        "subCategory": {"family": "Arial", "color": "#000000", "size": "0.85rem"},
        "card": {"family": "Arial", "color": "auto", "size": "0.75rem"},
    },
    "header": {
        "text": "",
        "background": "#1b5e20",
        "font": {"family": "Arial", "color": "#ffffff", "size": "1.5rem"},
    },
    "footer": {
        "text": "",
        "background": "#1b5e20",
        "font": {"family": "Arial", "color": "#ffffff", "size": "0.85rem"},
    },
    "watermark": {
        "dataUrl": None,
        "position": "bottom-right",
        "scale": 0.15,
        "opacity": 1,
    },
}
"""Camel-case JSON defaults; tests assert they equal ``Style()``."""


def _default_style() -> dict[str, Any]:
    return copy.deepcopy(_DEFAULT_STYLE)


def _merge_mapping(defaults: dict[str, Any], provided: object) -> object:
    """Overlay ``provided`` on ``defaults``, recursing into nested mappings.

    A non-mapping ``provided`` is returned unchanged so validation can report
    it. ``None`` values fall back to the default, except where the default
    itself is ``None`` (e.g. ``watermark.dataUrl``).
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


def _normalize_color(color: object) -> object:
    if not isinstance(color, dict):
        return color
    normalized: dict[str, Any] = dict(color)
    if normalized.get("id") is None:
        normalized["id"] = str(uuid.uuid4())
    return normalized


def _normalize_group(group: object, child_key: str | None) -> object:
    """Fill id and list fields of a category (``child_key``) or sub-category."""
    if not isinstance(group, dict):
        return group
    normalized: dict[str, Any] = dict(group)
    if normalized.get("id") is None:
        normalized["id"] = str(uuid.uuid4())
    colors = normalized.get("colors")
    if colors is None:
        normalized["colors"] = []
    elif isinstance(colors, list):
        normalized["colors"] = [_normalize_color(item) for item in colors]
    if child_key is not None:
        children = normalized.get(child_key)
        if children is None:
            normalized[child_key] = []
        elif isinstance(children, list):
            normalized[child_key] = [_normalize_group(item, None) for item in children]
    return normalized


def _normalize_category(category: object) -> object:
    return _normalize_group(category, "subCategories")


def normalize_document(raw: object) -> object:
    """Fill missing fields of a partial document mapping with defaults.

    Missing ``style`` values come from the TypeScript defaults; missing ids
    are generated.
    Required user data (``name``, ``hex``) is never invented, so validation
    still reports it. The input is not modified and this function never
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
    normalized["style"] = _merge_mapping(
        _default_style(), {} if style is None else style
    )
    return normalized
