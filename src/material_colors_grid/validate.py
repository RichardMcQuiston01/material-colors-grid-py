"""Validation of untrusted JSON-like data against the document shape."""

from __future__ import annotations

import json
import re
from typing import Any, Final

from material_colors_grid.models import ORIENTATIONS, WATERMARK_POSITIONS
from material_colors_grid.result import Err, Ok, Result
from material_colors_grid.units import css_size_to_px

_HEX_COLOR_PATTERN: Final = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


_INT_KEYS: Final = ("width", "height", "cardsPerRow")
_STYLE_KEYS: Final = (
    "orientation",
    "aspectRatio",
    *_INT_KEYS,
    "cardBackground",
    "border",
    "fonts",
    "header",
    "footer",
    "watermark",
)


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
    path: str, value: object, low: float, high: float
) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _invalid(path, value, "a number")
    if low <= value <= high:
        return None
    return _invalid(path, value, f"a number in [{low:g}, {high:g}]")


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


def _check_css_size(path: str, value: object) -> str | None:
    if isinstance(value, str):
        parsed = css_size_to_px(value)
        if isinstance(parsed, Ok) and parsed.value >= 0:
            return None
    return _invalid(path, value, 'a CSS size such as "1rem", "12px" or "12"')


def _check_bool(path: str, value: object) -> str | None:
    if isinstance(value, bool):
        return None
    return _invalid(path, value, "true or false")


def _check_choice(path: str, value: object, choices: tuple[str, ...]) -> str | None:
    if isinstance(value, str) and value in choices:
        return None
    return _invalid(path, value, "one of " + ", ".join(choices))


def _validate_object(path: str, value: object, keys: tuple[str, ...]) -> str | None:
    """Check ``value`` is an object that has every key in ``keys``."""
    mapping_error = _check_mapping(path, value)
    if mapping_error is not None or not isinstance(value, dict):
        return mapping_error
    for key in keys:
        missing = _require(value, path, key)
        if missing is not None:
            return missing
    return None


def _validate_group(path: str, group: object, child_key: str | None) -> str | None:
    """Validate a category (``child_key`` given) or a sub-category."""
    keys = ("id", "name", "colors") + (() if child_key is None else (child_key,))
    structure_error = _validate_object(path, group, keys)
    if structure_error is not None or not isinstance(group, dict):
        return structure_error
    checks = [
        _check_string(f"{path}.id", group["id"]),
        _check_string(f"{path}.name", group["name"]),
        _check_list(f"{path}.colors", group["colors"]),
    ]
    if child_key is not None:
        checks.append(_check_list(f"{path}.{child_key}", group[child_key]))
    shape_error = _first_error(checks)
    if shape_error is not None:
        return shape_error
    for index, color in enumerate(group["colors"]):
        error = _validate_color(f"{path}.colors[{index}]", color)
        if error is not None:
            return error
    if child_key is not None:
        for index, child in enumerate(group[child_key]):
            error = _validate_group(f"{path}.{child_key}[{index}]", child, None)
            if error is not None:
                return error
    return None


def _validate_category(path: str, category: object) -> str | None:
    return _validate_group(path, category, "subCategories")


def _validate_font(path: str, font: object, *, allow_auto: bool = False) -> str | None:
    structure_error = _validate_object(path, font, ("family", "color", "size"))
    if structure_error is not None or not isinstance(font, dict):
        return structure_error
    color = font["color"]
    if allow_auto and color == "auto":
        color_error = None
    elif allow_auto:
        color_error = (
            None
            if is_hex_color(color)
            else _invalid(f"{path}.color", color, '"auto" or 3 or 6 hex digits')
        )
    else:
        color_error = _check_hex(f"{path}.color", color)
    return _first_error(
        [
            _check_string(f"{path}.family", font["family"]),
            color_error,
            _check_css_size(f"{path}.size", font["size"]),
        ]
    )


def _validate_band(path: str, band: object) -> str | None:
    structure_error = _validate_object(path, band, ("text", "background", "font"))
    if structure_error is not None or not isinstance(band, dict):
        return structure_error
    return _first_error(
        [
            _check_string(f"{path}.text", band["text"]),
            _check_hex(f"{path}.background", band["background"]),
            _validate_font(f"{path}.font", band["font"]),
        ]
    )


def _validate_border(path: str, border: object) -> str | None:
    structure_error = _validate_object(path, border, ("rounded", "thickness", "color"))
    if structure_error is not None or not isinstance(border, dict):
        return structure_error
    return _first_error(
        [
            _check_bool(f"{path}.rounded", border["rounded"]),
            _check_css_size(f"{path}.thickness", border["thickness"]),
            _check_hex(f"{path}.color", border["color"]),
        ]
    )


def _validate_fonts(path: str, fonts: object) -> str | None:
    structure_error = _validate_object(path, fonts, ("category", "subCategory", "card"))
    if structure_error is not None or not isinstance(fonts, dict):
        return structure_error
    return _first_error(
        [
            _validate_font(f"{path}.category", fonts["category"]),
            _validate_font(f"{path}.subCategory", fonts["subCategory"]),
            _validate_font(f"{path}.card", fonts["card"], allow_auto=True),
        ]
    )


def _validate_watermark(path: str, watermark: object) -> str | None:
    structure_error = _validate_object(
        path, watermark, ("dataUrl", "position", "scale", "opacity")
    )
    if structure_error is not None or not isinstance(watermark, dict):
        return structure_error
    data_url = watermark["dataUrl"]
    data_url_error = (
        None if data_url is None else _check_string(f"{path}.dataUrl", data_url)
    )
    return _first_error(
        [
            data_url_error,
            _check_choice(
                f"{path}.position", watermark["position"], WATERMARK_POSITIONS
            ),
            _check_number_in_range(f"{path}.scale", watermark["scale"], 0, 1),
            _check_number_in_range(f"{path}.opacity", watermark["opacity"], 0, 1),
        ]
    )


def _validate_style(path: str, style: object) -> str | None:
    structure_error = _validate_object(path, style, _STYLE_KEYS)
    if structure_error is not None or not isinstance(style, dict):
        return structure_error
    errors: list[str | None] = [
        _check_choice(f"{path}.orientation", style["orientation"], ORIENTATIONS),
        _check_string(f"{path}.aspectRatio", style["aspectRatio"]),
    ]
    errors.extend(_check_int(f"{path}.{key}", style[key], 1) for key in _INT_KEYS)
    errors.extend(
        [
            _check_hex(f"{path}.cardBackground", style["cardBackground"]),
            _validate_border(f"{path}.border", style["border"]),
            _validate_fonts(f"{path}.fonts", style["fonts"]),
            _validate_band(f"{path}.header", style["header"]),
            _validate_band(f"{path}.footer", style["footer"]),
            _validate_watermark(f"{path}.watermark", style["watermark"]),
        ]
    )
    return _first_error(errors)


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
