"""Validation of untrusted JSON-like data against the document shape."""

from __future__ import annotations

import json
import re
from typing import Any, Final

from material_colors_grid.result import Err, Ok, Result

_HEX_COLOR_PATTERN: Final = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
_WATERMARK_POSITIONS: Final = (
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
    "center",
)
_POSITIVE_INT_STYLE_KEYS: Final = ("width", "height", "cards_per_row")
_NON_NEGATIVE_INT_STYLE_KEYS: Final = ("card_border_thickness", "card_corner_radius")
_HEX_STYLE_KEYS: Final = (
    "background_color",
    "card_background_color",
    "card_border_color",
)
_BAND_KEYS: Final = ("header", "footer")


def is_hex_color(value: object) -> bool:
    """Tell whether ``value`` is a 3- or 6-digit hex color with a leading ``#``.

    Args:
        value: Any object.

    Returns:
        ``True`` only for strings like ``"#fff"`` or ``"#1A2b3C"``. Everything
        else (no ``#``, 4/8 digits, non-hex digits, non-strings) is ``False``.
    """
    return isinstance(value, str) and _HEX_COLOR_PATTERN.fullmatch(value) is not None


def _describe(value: object) -> str:
    """Render a value for an error message, JSON style."""
    return json.dumps(value, ensure_ascii=False, default=repr)


def _invalid(path: str, value: object, expectation: str) -> str:
    return f"{path} {_describe(value)} is invalid (expected {expectation})"


def _check_string(path: str, value: object) -> str | None:
    if isinstance(value, str):
        return None
    return _invalid(path, value, "a string")


def _check_hex(path: str, value: object) -> str | None:
    if is_hex_color(value):
        return None
    return _invalid(path, value, "3 or 6 hex digits")


def _check_int(path: str, value: object, minimum: int) -> str | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= minimum:
        return None
    return _invalid(path, value, f"an integer >= {minimum}")


def _check_number_in_range(
    path: str, value: object, low: float, high: float, low_exclusive: bool
) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _invalid(path, value, "a number")
    above_low = value > low if low_exclusive else value >= low
    if above_low and value <= high:
        return None
    bracket = "(" if low_exclusive else "["
    return _invalid(path, value, f"a number in {bracket}{low}, {high}]")


def _check_mapping(path: str, value: object) -> str | None:
    if isinstance(value, dict):
        return None
    return _invalid(path, value, "an object")


def _check_list(path: str, value: object) -> str | None:
    if isinstance(value, list):
        return None
    return _invalid(path, value, "an array")


def _first_error(errors: list[str | None]) -> str | None:
    for error in errors:
        if error is not None:
            return error
    return None


def _require(mapping: dict[str, Any], path: str, key: str) -> str | None:
    if key in mapping:
        return None
    return f"{path}.{key} is missing" if path else f"{key} is missing"


def _validate_color(path: str, color: object) -> str | None:
    mapping_error = _check_mapping(path, color)
    if mapping_error is not None or not isinstance(color, dict):
        return mapping_error
    for key in ("id", "name", "hex"):
        missing = _require(color, path, key)
        if missing is not None:
            return missing
    return _first_error(
        [
            _check_string(f"{path}.id", color["id"]),
            _check_string(f"{path}.name", color["name"]),
            _check_hex(f"{path}.hex", color["hex"]),
        ]
    )


def _validate_category(path: str, category: object) -> str | None:
    mapping_error = _check_mapping(path, category)
    if mapping_error is not None or not isinstance(category, dict):
        return mapping_error
    for key in ("id", "name", "colors", "sub_categories"):
        missing = _require(category, path, key)
        if missing is not None:
            return missing
    shape_error = _first_error(
        [
            _check_string(f"{path}.id", category["id"]),
            _check_string(f"{path}.name", category["name"]),
            _check_list(f"{path}.colors", category["colors"]),
            _check_list(f"{path}.sub_categories", category["sub_categories"]),
        ]
    )
    if shape_error is not None:
        return shape_error
    for index, color in enumerate(category["colors"]):
        error = _validate_color(f"{path}.colors[{index}]", color)
        if error is not None:
            return error
    for index, sub_category in enumerate(category["sub_categories"]):
        error = _validate_category(f"{path}.sub_categories[{index}]", sub_category)
        if error is not None:
            return error
    return None


def _validate_band(path: str, band: object) -> str | None:
    mapping_error = _check_mapping(path, band)
    if mapping_error is not None or not isinstance(band, dict):
        return mapping_error
    for key in ("text", "background_color", "font_color"):
        missing = _require(band, path, key)
        if missing is not None:
            return missing
    return _first_error(
        [
            _check_string(f"{path}.text", band["text"]),
            _check_hex(f"{path}.background_color", band["background_color"]),
            _check_hex(f"{path}.font_color", band["font_color"]),
        ]
    )


def _validate_watermark(path: str, watermark: object) -> str | None:
    mapping_error = _check_mapping(path, watermark)
    if mapping_error is not None or not isinstance(watermark, dict):
        return mapping_error
    for key in ("image_path", "position", "scale", "opacity"):
        missing = _require(watermark, path, key)
        if missing is not None:
            return missing
    image_path = watermark["image_path"]
    image_path_error = (
        None if image_path is None else _check_string(f"{path}.image_path", image_path)
    )
    position = watermark["position"]
    position_error = (
        None
        if position in _WATERMARK_POSITIONS
        else _invalid(
            f"{path}.position",
            position,
            "one of " + ", ".join(_WATERMARK_POSITIONS),
        )
    )
    return _first_error(
        [
            image_path_error,
            position_error,
            _check_number_in_range(f"{path}.scale", watermark["scale"], 0, 1, True),
            _check_number_in_range(
                f"{path}.opacity", watermark["opacity"], 0, 1, False
            ),
        ]
    )


def _validate_style(path: str, style: object) -> str | None:
    mapping_error = _check_mapping(path, style)
    if mapping_error is not None or not isinstance(style, dict):
        return mapping_error
    required = (
        *_POSITIVE_INT_STYLE_KEYS,
        *_NON_NEGATIVE_INT_STYLE_KEYS,
        *_HEX_STYLE_KEYS,
        "card_font_color",
        *_BAND_KEYS,
        "watermark",
    )
    for key in required:
        missing = _require(style, path, key)
        if missing is not None:
            return missing
    for key in _POSITIVE_INT_STYLE_KEYS:
        error = _check_int(f"{path}.{key}", style[key], 1)
        if error is not None:
            return error
    for key in _NON_NEGATIVE_INT_STYLE_KEYS:
        error = _check_int(f"{path}.{key}", style[key], 0)
        if error is not None:
            return error
    for key in _HEX_STYLE_KEYS:
        error = _check_hex(f"{path}.{key}", style[key])
        if error is not None:
            return error
    font_color = style["card_font_color"]
    if font_color != "auto" and not is_hex_color(font_color):
        return _invalid(
            f"{path}.card_font_color", font_color, '"auto" or 3 or 6 hex digits'
        )
    for key in _BAND_KEYS:
        error = _validate_band(f"{path}.{key}", style[key])
        if error is not None:
            return error
    return _validate_watermark(f"{path}.watermark", style["watermark"])


def validate_project_document(raw: object) -> Result[dict[str, Any]]:
    """Validate a complete (already normalized) document mapping.

    Args:
        raw: Untrusted data, typically from ``json.loads`` after
            ``normalize_document``.

    Returns:
        ``Ok`` with the same mapping when valid. ``Err`` with a message naming
        the JSON path and the offending value, for example
        ``categories[0].colors[2].hex "#12" is invalid (expected 3 or 6 hex
        digits)``. Never raises.
    """
    if not isinstance(raw, dict):
        return Err(_invalid("document", raw, "an object"))
    for key in ("categories", "style"):
        missing = _require(raw, "", key)
        if missing is not None:
            return Err(missing)
    list_error = _check_list("categories", raw["categories"])
    if list_error is not None:
        return Err(list_error)
    for index, category in enumerate(raw["categories"]):
        error = _validate_category(f"categories[{index}]", category)
        if error is not None:
            return Err(error)
    style_error = _validate_style("style", raw["style"])
    if style_error is not None:
        return Err(style_error)
    return Ok(raw)


def is_project_document(raw: object) -> bool:
    """Tell whether ``raw`` is a valid, complete document mapping.

    Args:
        raw: Any object, typically parsed JSON.

    Returns:
        ``True`` when ``validate_project_document`` would succeed.
    """
    return isinstance(validate_project_document(raw), Ok)
